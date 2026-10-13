"""Validate independent Compose stacks without reading runtime settings."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import yaml


COMPOSE_NAMES = {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}
VARIABLE = re.compile(
    r"\$\$|\$(?:\{(?P<braced>[A-Za-z_]\w*)"
    r"(?P<operator>:-|-|:\+|\+|:\?|\?)?[^}]*\}|(?P<bare>[A-Za-z_]\w*))"
)
DATABASE_IMAGES = {"postgres", "mariadb", "mysql", "mongo", "redis", "valkey"}


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class Image:
    repository: str
    tag: str | None
    digest: str | None


@dataclass(frozen=True)
class ImageChange:
    file: str
    service: str
    before: str | None
    after: str | None


def run(arguments, *, root, environment=None, text=None):
    result = subprocess.run(
        arguments, cwd=root, env=environment, input=text,
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        raise ValidationError(result.stderr.strip() or f"Command failed: {arguments[0]}")
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.stdout


def compose_files(root, base_ref=None):
    if base_ref:
        output = run(["git", "ls-tree", "-rz", "--name-only", base_ref], root=root)
    else:
        output = run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            root=root,
        )
    return sorted({
        name for name in output.split("\0")
        if name and Path(name).name in COMPOSE_NAMES
        and (base_ref or (root / name).is_file())
    })


def parse_document(text):
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValidationError(f"Invalid Compose YAML: {error.problem}") from error
    if not isinstance(document, dict):
        raise ValidationError("Compose YAML must be a mapping.")
    if "include" in document:
        raise ValidationError("include is unsupported: use an independent stack file.")
    services = document.get("services", {})
    if isinstance(services, dict):
        for service in services.values():
            if isinstance(service, dict) and "extends" in service:
                raise ValidationError("extends is unsupported: use an independent stack file.")
    return document


def scalar_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from scalar_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from scalar_strings(item)


def dummy_value(name):
    if name in {"UID", "GID", "PUID", "PGID"}:
        return "3001"
    if name == "PORT" or name.endswith("_PORT"):
        return "18000"
    if name == "SUBNET" or name.endswith("_SUBNET"):
        return "192.0.2.0/24"
    if name == "GATEWAY" or name.endswith("_GATEWAY"):
        return "192.0.2.1"
    if name == "IP" or name.endswith("_IP"):
        return "192.0.2.5"
    if name.endswith(("_PATH", "_DIR")):
        return "/validation-only"
    if name.endswith("_URL"):
        return "https://validation.example.invalid"
    if name.endswith(("_DOMAIN", "_HOST")):
        return "validation.example.invalid"
    if name.endswith("_EMAIL"):
        return "validation@example.invalid"
    if name == "TZ":
        return "Etc/UTC"
    return "validation-only-not-a-secret"


def dummy_environment(document, config_directory):
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "PATHEXT", "COMSPEC",
        }
    }
    environment.update({
        "HOME": str(config_directory),
        "DOCKER_CONFIG": str(config_directory),
        "COMPOSE_DISABLE_ENV_FILE": "1",
    })
    for value in scalar_strings(document):
        for match in VARIABLE.finditer(value):
            name = match["braced"] or match["bare"]
            if name and match["operator"] not in {":-", "-", ":+", "+"}:
                environment[name] = dummy_value(name)
    return environment


def prepare_docker_config(config_directory):
    executable = shutil.which("docker")
    if not executable:
        raise ValidationError("Docker CLI is not installed or is not on PATH.")
    plugin_name = "docker-compose.exe" if os.name == "nt" else "docker-compose"
    candidates = (
        Path(executable).resolve().parent.parent / "cli-plugins",
        Path.home() / ".docker" / "cli-plugins",
    )
    directories = [str(path) for path in candidates if (path / plugin_name).is_file()]
    if directories:
        (config_directory / "config.json").write_text(
            json.dumps({"cliPluginsExtraDirs": directories}), encoding="utf-8",
        )


def parse_image(reference):
    if any(character.isspace() for character in reference) or "://" in reference:
        raise ValidationError("Image reference contains whitespace or a URL scheme.")
    name, separator, digest = reference.partition("@")
    if separator and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValidationError("Image digest must be sha256 followed by 64 lowercase hex characters.")
    repository, colon, tag = name.rpartition(":")
    if not colon or "/" in tag:
        repository, tag = name, None
    if not repository or (colon and tag == ""):
        raise ValidationError("Image repository or tag is empty.")
    return Image(repository, tag, digest if separator else None)


def validate_images(images):
    nextcloud = []
    for service, reference in images.items():
        try:
            image = parse_image(reference)
        except ValidationError as error:
            raise ValidationError(f"{service}: {error}") from error
        if image.repository.rsplit("/", 1)[-1] == "nextcloud":
            nextcloud.append(reference)
    if len(set(nextcloud)) > 1:
        raise ValidationError("Nextcloud application and cron services must use identical images.")


def render_images(root, file, text, config_directory):
    document = parse_document(text)
    environment = dummy_environment(document, config_directory)
    output = run(
        [
            "docker", "compose", "--env-file", os.devnull,
            "--project-directory", str((root / file).parent),
            "--profile", "*", "-f", "-", "config",
            "--no-env-resolution", "--no-path-resolution", "--format", "json",
        ],
        root=root, environment=environment, text=text,
    )
    try:
        model = json.loads(output)
    except json.JSONDecodeError as error:
        raise ValidationError("Docker Compose did not return valid JSON.") from error
    images = {
        name: service["image"] for name, service in model["services"].items()
        if "image" in service
    }
    validate_images(images)
    return images


def image_changes(before, after):
    changes = []
    for file in sorted(before.keys() | after.keys()):
        old_services, new_services = before.get(file, {}), after.get(file, {})
        for service in sorted(old_services.keys() | new_services.keys()):
            old, new = old_services.get(service), new_services.get(service)
            if old != new:
                changes.append(ImageChange(file, service, old, new))
    return changes


def image_warnings(change):
    if change.before is None:
        return ["Service/image added; review prerequisites and persistent storage."]
    if change.after is None:
        return ["Service/image removed; review data retention and rollback."]
    old, new = parse_image(change.before), parse_image(change.after)
    warnings = []
    if old.repository != new.repository:
        warnings.append("Image repository changed; review compatibility and migration.")
    if old.digest and old.digest == new.digest and old.tag != new.tag:
        warnings.append("Tag changed but digest did not; the selected content is unchanged.")
    old_major = re.match(r"^v?(\d+)(?:[.-]|$)", old.tag or "")
    new_major = re.match(r"^v?(\d+)(?:[.-]|$)", new.tag or "")
    if old_major and new_major:
        if old_major[1] != new_major[1]:
            if new.repository.rsplit("/", 1)[-1] in DATABASE_IMAGES:
                warnings.append("Database major changed; review migration, backup, and rollback before merge.")
            else:
                warnings.append("Major tag number changed; check for breaking changes.")
    else:
        warnings.append("Version change cannot be classified from these tags/digests; review the upstream release.")
    return warnings


def markdown_cell(value):
    if value is None:
        return "(absent)"
    return value.replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ").replace("\r", " ")


def annotation(level, message):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{level}::{escaped}")
    else:
        print(f"{level.upper()}: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="", help="Git commit/ref to compare images against.")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    errors = []
    after = {}
    before = {}
    with tempfile.TemporaryDirectory(prefix="homelab-compose-") as directory:
        config_directory = Path(directory)
        prepare_docker_config(config_directory)
        environment = dummy_environment({}, config_directory)
        help_text = run(["docker", "compose", "config", "--help"], root=root, environment=environment)
        if "--no-env-resolution" not in help_text or "--no-path-resolution" not in help_text:
            raise ValidationError("Upgrade Docker Compose: config needs --no-env-resolution and --no-path-resolution.")
        files = compose_files(root)
        if not files:
            raise ValidationError("No Compose stacks found.")
        for file in files:
            try:
                if not (root / file).with_name(".env.example").is_file():
                    raise ValidationError("Missing .env.example template.")
                after[file] = render_images(
                    root, file, (root / file).read_text(encoding="utf-8"), config_directory,
                )
                print(f"PASS: {file}")
            except ValidationError as error:
                errors.append(f"{file}: {error}")
        if arguments.base_ref and not errors:
            base_ref = run(
                ["git", "rev-parse", "--verify", f"{arguments.base_ref}^{{commit}}"], root=root,
            ).strip()
            for file in compose_files(root, base_ref):
                text = run(["git", "show", f"{base_ref}:{file}"], root=root)
                before[file] = render_images(root, file, text, config_directory)
    changes = image_changes(before, after) if arguments.base_ref and not errors else []
    summary = [
        "# Compose validation", "",
        f"Validated {len(after)} of {len(files)} stacks with dummy settings.", "",
        "Static checks only: no image pulls, container starts, live health checks, or database migrations.", "",
    ]
    if errors:
        summary.extend(["## Failures", ""])
        for error in errors:
            annotation("error", error)
            summary.append(f"- {markdown_cell(error)}")
    if arguments.base_ref and not errors:
        summary.extend([
            "## Image changes", "",
            "| Stack | Service | Before | After | Review |",
            "| --- | --- | --- | --- | --- |",
        ])
        for change in changes:
            warnings = image_warnings(change)
            for warning in warnings:
                annotation("warning", f"{change.file} / {change.service}: {warning}")
            review = " ".join(warnings) or "Review release notes and backup requirements."
            summary.append("| " + " | ".join(markdown_cell(value) for value in (
                change.file, change.service, change.before, change.after, review,
            )) + " |")
        if not changes:
            summary.append("| - | - | - | - | No image changes. |")
    elif not errors:
        summary.append("Image comparison skipped: no --base-ref was supplied.")
    summary.extend([
        "", "Warnings require human review; they do not block this check.",
        "Passing checks do not establish image availability, application compatibility, or migration safety.",
    ])
    report = "\n".join(summary) + "\n"
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(report, encoding="utf-8")
    else:
        print(report)
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValidationError, OSError) as error:
        annotation("error", str(error))
        sys.exit(1)
