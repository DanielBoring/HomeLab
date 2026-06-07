#!/usr/bin/env python3
"""Generate Traefik Manager dashboard group overrides from live routes.

Traefik Manager stores dashboard customisation in /app/config/dashboard.yml.
This helper keeps group intent in dashboard-groups.json, resolves live route IDs
from the Traefik Manager API, and writes only the keys Traefik Manager supports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_GROUPS = Path(__file__).with_name("dashboard-groups.json")
DEFAULT_OUTPUT = Path("/mnt/SSD/Containers/traefik-manager/config/dashboard.yml")


def normalise_name(value: str) -> str:
    value = (value or "").strip().lower()
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        value = value.replace(dash, "-")
    if "@" in value:
        value = value.split("@", 1)[0]
    return value


def load_group_policy(path: Path) -> tuple[dict[str, str], set[str]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    route_to_group: dict[str, str] = {}
    for group, names in data.get("groups", {}).items():
        for name in names:
            key = normalise_name(str(name))
            if key in route_to_group:
                raise ValueError(
                    f"Route {name!r} is assigned to both "
                    f"{route_to_group[key]!r} and {group!r}."
                )
            route_to_group[key] = str(group)

    intentional_skips = {normalise_name(str(name)) for name in data.get("intentional_skips", [])}
    return route_to_group, intentional_skips


def fetch_routes(api_url: str, timeout: int, api_key: str | None) -> list[dict[str, Any]]:
    url = urljoin(api_url.rstrip("/") + "/", "api/routes/all")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller supplies internal URL
        payload = json.loads(response.read().decode("utf-8"))
    routes = payload.get("apps", payload if isinstance(payload, list) else [])
    if not isinstance(routes, list):
        raise ValueError(f"Unexpected route payload from {url}: expected list or apps list")
    return [route for route in routes if isinstance(route, dict)]


def load_routes_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    routes = payload.get("apps", payload if isinstance(payload, list) else [])
    if not isinstance(routes, list):
        raise ValueError("Route JSON must be a list or an object with an apps list")
    return [route for route in routes if isinstance(route, dict)]


def load_routes_from_markdown(path: Path) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    service_column = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.startswith("|") or "|" not in stripped[1:]:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not cells:
                continue
            if cells[0].lower() == "service":
                service_column = 0
                continue
            if set(cells[0].replace("-", "")) == set():
                continue
            if service_column is None:
                continue
            name = cells[service_column].strip()
            if not name or name.startswith("+") or name == "—":
                continue
            name = normalise_name(name)
            routes.append({"id": name, "name": name, "service_name": name})
    return routes


def route_names(route: dict[str, Any]) -> list[str]:
    names = [
        str(route.get("name", "")),
        str(route.get("id", "")),
        str(route.get("service_name", "")),
    ]
    result: list[str] = []
    for name in names:
        key = normalise_name(name)
        if key and key not in result:
            result.append(key)
    return result


def group_for_route(route: dict[str, Any], route_to_group: dict[str, str]) -> str | None:
    for key in route_names(route):
        if key in route_to_group:
            return route_to_group[key]
    return None


def route_id(route: dict[str, Any]) -> str:
    value = str(route.get("id") or route.get("name") or "").strip()
    if not value:
        raise ValueError(f"Route is missing both id and name: {route!r}")
    return value


def yaml_scalar(value: str) -> str:
    if re.match(r"^[A-Za-z0-9_.:@/-]+$", value):
        return value
    return json.dumps(value)


def render_dashboard_yaml(route_overrides: dict[str, str]) -> str:
    lines = ["custom_groups: []", "route_overrides:"]
    if not route_overrides:
        lines.append("  {}");
        return "\n".join(lines) + "\n"
    for rid in sorted(route_overrides, key=str.lower):
        lines.append(f"  {yaml_scalar(rid)}:")
        lines.append(f"    group: {yaml_scalar(route_overrides[rid])}")
    return "\n".join(lines) + "\n"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    tmp.replace(path)


def print_summary(route_count: int, overrides: dict[str, str], unmatched: list[str], skipped: list[str]) -> None:
    print(f"Routes read: {route_count}")
    print(f"Routes grouped: {len(overrides)}")
    if skipped:
        print("Intentional skips: " + ", ".join(sorted(skipped, key=str.lower)))
    if unmatched:
        print("Unmatched routes: " + ", ".join(sorted(unmatched, key=str.lower)))
    else:
        print("Unmatched routes: none")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Generate Traefik Manager dashboard.yml group overrides.")
    parser.add_argument("--groups", type=Path, default=DEFAULT_GROUPS, help="Canonical grouping JSON file.")
    parser.add_argument("--api-url", help="Traefik Manager base URL, e.g. https://traefik-manager.example.com")
    parser.add_argument("--api-key", help="Optional Traefik Manager API bearer token.")
    parser.add_argument("--routes-json", type=Path, help="Offline routes JSON from /api/routes/all.")
    parser.add_argument("--routes-md", type=Path, help="Offline Markdown dashboard export to audit names only.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="dashboard.yml output path.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated YAML instead of writing it.")
    parser.add_argument("--timeout", type=int, default=10, help="API request timeout in seconds.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when unmatched routes remain.")
    args = parser.parse_args()

    sources = [bool(args.api_url), bool(args.routes_json), bool(args.routes_md)]
    if sum(sources) != 1:
        parser.error("Choose exactly one route source: --api-url, --routes-json, or --routes-md")

    route_to_group, intentional_skips = load_group_policy(args.groups)
    try:
        if args.api_url:
            routes = fetch_routes(args.api_url, args.timeout, args.api_key)
        elif args.routes_json:
            routes = load_routes_json(args.routes_json)
        else:
            routes = load_routes_from_markdown(args.routes_md)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Failed to read routes: {exc}", file=sys.stderr)
        return 2

    overrides: dict[str, str] = {}
    unmatched: list[str] = []
    skipped: list[str] = []

    for route in routes:
        names = route_names(route)
        if any(name in intentional_skips for name in names):
            skipped.append(route.get("name") or route.get("id") or names[0])
            continue
        group = group_for_route(route, route_to_group)
        if group:
            overrides[route_id(route)] = group
        else:
            unmatched.append(route.get("name") or route.get("id") or "/".join(names))

    content = render_dashboard_yaml(overrides)
    print_summary(len(routes), overrides, unmatched, skipped)

    if args.dry_run:
        print("\n--- dashboard.yml preview ---")
        print(content, end="")
    else:
        write_atomic(args.output, content)
        print(f"Wrote {args.output}")

    if args.strict and unmatched:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



