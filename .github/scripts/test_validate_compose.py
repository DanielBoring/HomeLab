from pathlib import Path
from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from unittest.mock import patch

import validate_compose as checker


class DummyEnvironmentTests(unittest.TestCase):
    def environment(self, text):
        return checker.dummy_environment(checker.parse_document(text), Path("empty-docker-config"))

    def test_runtime_settings_are_not_inherited(self):
        with patch.dict(checker.os.environ, {
            "POSTGRES_PASSWORD": "runtime-secret",
            "UNRELATED_SECRET": "runtime-secret",
            "DOCKER_HOST": "tcp://runtime-host",
            "COMPOSE_FILE": "private.yaml",
            "COMPOSE_ENV_FILES": ".env",
            "PATH": "tool-path",
        }, clear=True):
            result = self.environment("services:\n  db:\n    environment:\n      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}")
        self.assertEqual(result["POSTGRES_PASSWORD"], "validation-only-not-a-secret")
        for key in ("UNRELATED_SECRET", "DOCKER_HOST", "COMPOSE_FILE", "COMPOSE_ENV_FILES"):
            self.assertNotIn(key, result)
        self.assertEqual(result["PATH"], "tool-path")
        self.assertEqual(result["COMPOSE_DISABLE_ENV_FILE"], "1")
        self.assertEqual(result["DOCKER_CONFIG"], "empty-docker-config")

    def test_defaults_and_escaped_variables_are_preserved(self):
        result = self.environment("""
services:
  app:
    image: app:${APP_VERSION:-v1.2.3}
    environment:
      - OPTIONAL=${OPTIONAL-default}
      - ALTERNATE=${ALTERNATE:+enabled}
    command: echo $$RUNTIME_VAR $${ESCAPED_VAR}
# ${COMMENT_ONLY}
""")
        for key in ("APP_VERSION", "OPTIONAL", "ALTERNATE", "RUNTIME_VAR", "ESCAPED_VAR", "COMMENT_ONLY"):
            self.assertNotIn(key, result)

    def test_required_and_bare_variables_receive_dummy_values(self):
        result = self.environment("""
services:
  app:
    environment:
      - KEY=${KEY:?Set KEY}
      - OTHER=${OTHER?Set OTHER}
      - DOMAIN=$APP_DOMAIN
      - PORT=${APP_PORT}
      - DATA=${DATA_PATH}
      - TZ=${TZ}
""")
        self.assertEqual(result["APP_PORT"], "18000")
        self.assertEqual(result["APP_DOMAIN"], "validation.example.invalid")
        self.assertEqual(result["DATA_PATH"], "/validation-only")
        self.assertEqual(result["TZ"], "Etc/UTC")
        self.assertEqual(result["KEY"], "validation-only-not-a-secret")
        self.assertEqual(result["OTHER"], "validation-only-not-a-secret")

    def test_required_use_overrides_optional_use_of_same_variable(self):
        result = self.environment('services:\n  app:\n    environment: ["${VALUE:-fallback}", "${VALUE}"]')
        self.assertEqual(result["VALUE"], "validation-only-not-a-secret")

    def test_extra_compose_sources_are_rejected(self):
        for text in (
            "include: other.yaml\nservices: {}",
            '{"include": ["other.yaml"], "services": {}}',
            "services:\n  app:\n    extends:\n      file: other.yaml\n      service: app",
        ):
            with self.subTest(text=text), self.assertRaises(checker.ValidationError):
                self.environment(text)


class ImageTests(unittest.TestCase):
    digest = "sha256:" + "a" * 64

    def test_image_reference_forms(self):
        examples = (
            ("postgres:17.11", "postgres", "17.11", None),
            ("registry.example:5000/team/app:v1.2.3", "registry.example:5000/team/app", "v1.2.3", None),
            ("registry.example:5000/team/app", "registry.example:5000/team/app", None, None),
            (f"app@{self.digest}", "app", None, self.digest),
            (f"app:v1.2.3@{self.digest}", "app", "v1.2.3", self.digest),
        )
        for reference, repository, tag, digest in examples:
            with self.subTest(reference=reference):
                self.assertEqual(checker.parse_image(reference), checker.Image(repository, tag, digest))

    def test_bad_fingerprints_are_rejected(self):
        for reference in ("app@sha256:abc", "app@sha256:" + "g" * 64, "app:", "app:bad tag", "https://registry/app"):
            with self.subTest(reference=reference), self.assertRaises(checker.ValidationError):
                checker.parse_image(reference)

    def test_nextcloud_pins_must_match(self):
        with self.assertRaises(checker.ValidationError):
            checker.validate_images({"app": "nextcloud:34.0.4", "cron": "nextcloud:34.0.3"})
        checker.validate_images({"app": f"nextcloud:34.0.4@{self.digest}", "cron": f"nextcloud:34.0.4@{self.digest}"})

    def test_database_major_warning(self):
        change = checker.ImageChange("db/compose.yaml", "db", "postgres:17.11", "postgres:18.0")
        self.assertTrue(any("Database major changed" in value for value in checker.image_warnings(change)))

    def test_patch_update_does_not_claim_major_change(self):
        change = checker.ImageChange("db/compose.yaml", "db", "postgres:17.10", "postgres:17.11")
        self.assertEqual(checker.image_warnings(change), [])

    def test_digest_only_update_requires_manual_classification(self):
        change = checker.ImageChange("app/compose.yaml", "app", f"app@{self.digest}", "app@sha256:" + "b" * 64)
        self.assertTrue(any("cannot be classified" in value for value in checker.image_warnings(change)))

    def test_tag_change_with_same_digest_is_flagged(self):
        change = checker.ImageChange("app/compose.yaml", "app", f"app:1.0@{self.digest}", f"app:2.0@{self.digest}")
        self.assertTrue(any("content is unchanged" in value for value in checker.image_warnings(change)))

    def test_added_removed_and_changed_services_are_reported(self):
        before = {"a/compose.yaml": {"old": "app:1", "same": "other:1"}}
        after = {"a/compose.yaml": {"new": "app:2", "same": "other:1"}}
        self.assertEqual(checker.image_changes(before, after), [
            checker.ImageChange("a/compose.yaml", "new", None, "app:2"),
            checker.ImageChange("a/compose.yaml", "old", "app:1", None),
        ])

    def test_renamed_repository_is_flagged(self):
        change = checker.ImageChange("app/compose.yaml", "app", "vendor/old:1", "vendor/new:1")
        self.assertTrue(any("repository changed" in value for value in checker.image_warnings(change)))


class ComposeInvocationTests(unittest.TestCase):
    @patch.object(checker, "run")
    def test_service_env_sources_are_neutralized_without_losing_schema(self, run):
        run.return_value = '{"services": {"app": {"image": "app:1"}}}'
        with tempfile.TemporaryDirectory(prefix="compose-env-isolation-") as directory:
            config = Path(directory)
            checker.render_images(Path.cwd(), "app/compose.yaml", """
services:
  app:
    image: app:1
    env_file:
      - private-runtime.env
      - path: another-private.env
        required: false
        format: raw
""", config)
            model = checker.parse_document(run.call_args.kwargs["text"])
            sources = model["services"]["app"]["env_file"]
            self.assertEqual(sources, [
                str((config / "empty-service.env").resolve()),
                {"path": str((config / "empty-service.env").resolve()),
                 "required": False, "format": "raw"},
            ])
            self.assertEqual((config / "empty-service.env").read_text(), "")

    @patch.object(checker.subprocess, "run")
    def test_commands_use_utf8_on_windows_and_linux(self, run):
        run.return_value = checker.subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        checker.run(["docker", "compose", "config"], root=Path.cwd(), text="# \u2713")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    @patch.object(checker.shutil, "which")
    def test_plugin_discovery_does_not_copy_user_credentials(self, which):
        which.return_value = str(Path.cwd() / "docker" / "bin" / "docker")
        with tempfile.TemporaryDirectory(prefix="compose-checker-test-") as directory:
            with patch.object(Path, "is_file", side_effect=[True, False]):
                checker.prepare_docker_config(Path(directory))
            config = json.loads((Path(directory) / "config.json").read_text())
            self.assertEqual(config, {
                "cliPluginsExtraDirs": [str(Path.cwd() / "docker" / "cli-plugins")],
            })

    @patch.object(checker, "run")
    def test_only_safe_compose_config_options_are_used(self, run):
        run.return_value = '{"services": {"app": {"image": "app:1"}}}'
        root = Path.cwd()
        result = checker.render_images(
            root, "app/compose.yaml", "services:\n  app:\n    image: app:1",
            Path("empty-docker-config"),
        )
        self.assertEqual(result, {"app": "app:1"})
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:4], ["docker", "compose", "--env-file", checker.os.devnull])
        for option in ("--no-env-resolution", "--no-path-resolution", "--format", "--profile"):
            self.assertIn(option, arguments)
        self.assertEqual(arguments[arguments.index("--profile") + 1], "*")
        for option in ("up", "pull", "down", "--resolve-image-digests"):
            self.assertNotIn(option, arguments)

    @patch.object(checker, "run")
    def test_discovery_ignores_deleted_stacks_and_includes_new_ones(self, run):
        run.return_value = "removed/compose.yaml\0new/compose.yaml\0new/README.md\0"
        with patch.object(Path, "is_file", side_effect=[False, True]):
            self.assertEqual(checker.compose_files(Path.cwd()), ["new/compose.yaml"])


class ComposeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="compose-checker-integration-")
        cls.root = Path(cls.directory.name)
        cls.config = cls.root / "docker-config"
        cls.config.mkdir()
        checker.prepare_docker_config(cls.config)
        (cls.root / "stack").mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def render(self, text):
        return checker.render_images(self.root, "stack/compose.yaml", text, self.config)

    def test_default_dotenv_and_missing_service_env_file_are_not_loaded(self):
        (self.root / "stack" / ".env").write_text("APP_VERSION=unreviewed-test-value\n")
        images = self.render("""
services:
  app:
    image: example/app:${APP_VERSION:-1.0}
    env_file:
      - missing-runtime.env
""")
        self.assertEqual(images, {"app": "example/app:1.0"})

    def test_profile_services_are_included(self):
        images = self.render("""
services:
  app:
    image: example/app:1.0
  optional:
    image: example/optional:1.0
    profiles: [manual]
""")
        self.assertEqual(set(images), {"app", "optional"})

    def test_invalid_compose_settings_fail(self):
        with self.assertRaises(checker.ValidationError):
            self.render("""
services:
  app:
    image: example/app:1.0
    unsupported_setting: true
""")

    def test_invalid_service_env_file_schema_fails(self):
        for source in ("42", "{required: false}", "{path: 42}", "{path: private.env, unsupported: true}"):
            with self.subTest(source=source), self.assertRaises(checker.ValidationError):
                self.render(f"services:\n  app:\n    image: example/app:1.0\n    env_file: [{source}]\n")

    def test_long_and_short_env_file_forms_are_not_loaded(self):
        for source in ("private-runtime.env", "[{path: private-runtime.env, required: true}]"):
            with self.subTest(source=source):
                self.assertEqual(
                    self.render(f"services:\n  app:\n    image: example/app:1.0\n    env_file: {source}\n"),
                    {"app": "example/app:1.0"},
                )


class ReportingTests(unittest.TestCase):
    def run_check(self, root, renders):
        stack = root / "stack"
        stack.mkdir()
        (stack / "compose.yaml").write_text("services: {}\n")
        (stack / ".env.example").write_text("# Synthetic test template\n")
        summary = root / "summary.md"
        with (
            patch.object(checker, "__file__", str(root / ".github" / "scripts" / "validate_compose.py")),
            patch.object(checker, "prepare_docker_config"),
            patch.object(checker, "compose_files", return_value=["stack/compose.yaml"]),
            patch.object(checker, "render_images", side_effect=renders),
            patch.object(checker, "run", side_effect=[
                "--no-env-resolution --no-path-resolution", "a" * 40, "services: {}",
            ]),
            patch.object(checker.sys, "argv", ["checker", "--base-ref", "HEAD"]),
            patch.dict(checker.os.environ, {
                "GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary),
            }),
            redirect_stdout(io.StringIO()),
        ):
            result = checker.main()
        return result, summary.read_text(encoding="utf-8")

    def test_image_warning_is_written_to_github_summary(self):
        with tempfile.TemporaryDirectory(prefix="compose-summary-test-") as directory:
            result, summary = self.run_check(Path(directory), [
                {"db": "postgres:18.0"}, {"db": "postgres:17.11"},
            ])
        self.assertEqual(result, 0)
        for value in ("Validated 1 of 1", "postgres:17.11", "postgres:18.0", "Database major changed"):
            self.assertIn(value, summary)

    def test_invalid_stack_fails_and_is_written_to_summary(self):
        with tempfile.TemporaryDirectory(prefix="compose-summary-test-") as directory:
            result, summary = self.run_check(Path(directory), [
                checker.ValidationError("unsupported setting"),
            ])
        self.assertEqual(result, 1)
        self.assertIn("## Failures", summary)
        self.assertIn("unsupported setting", summary)


if __name__ == "__main__":
    unittest.main()
