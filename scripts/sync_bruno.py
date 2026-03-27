#!/usr/bin/env python3
"""
Sync Bruno collection from the running API's OpenAPI spec.
Run `make dev` first, then `make bruno-sync`.

Usage: python scripts/sync_bruno.py
"""

import json
import re
import shutil
import sys
from pathlib import Path

import urllib.request
import urllib.error

OPENAPI_URL = "http://localhost:8000/openapi.json"
BRUNO_DIR = Path(__file__).parent.parent / "bruno"
ENVIRONMENTS_DIR = BRUNO_DIR / "environments"

# Maps OpenAPI security scheme names to Bruno header names
AUTH_HEADERS = {
    "x-api-key": ("X-API-Key", "{{api-key}}"),
    "x-admin-secret": ("X-Admin-Secret", "{{admin-secret}}"),
}


def fetch_openapi() -> dict:
    try:
        with urllib.request.urlopen(OPENAPI_URL, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError:
        print("ERROR: Could not reach the API. Is `make dev` running?")
        sys.exit(1)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text


def get_auth_header(path: str) -> tuple[str, str] | None:
    """Infer auth header from path prefix."""
    if path.startswith("/admin/"):
        return ("X-Admin-Secret", "{{admin-secret}}")
    if path.startswith("/api/"):
        return ("X-API-Key", "{{api-key}}")
    return None


def path_to_folder(path: str) -> str:
    """Convert /api/v1/lesson-plans to lesson-plans, /admin/clients to admin."""
    parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
    # Drop versioning prefix (api/v1)
    if parts and parts[0] == "api":
        parts = parts[2:]  # drop 'api' and 'v1'
    if not parts:
        return "misc"
    return parts[0]


def build_bru(method: str, path: str, operation: dict, spec: dict) -> str:
    name = operation.get("summary") or f"{method.upper()} {path}"
    auth_header = get_auth_header(path)

    has_body = method.lower() in ("post", "put", "patch")

    lines = [
        f"meta {{",
        f"  name: {name}",
        f"  type: http",
        f"  seq: 1",
        f"}}",
        f"",
        f"{method.lower()} {{",
        f"  url: {{{{base-url}}}}{path}",
        f"  body: {'json' if has_body else 'none'}",
        f"  auth: none",
        f"}}",
    ]

    if auth_header:
        lines += [
            f"",
            f"headers {{",
            f"  {auth_header[0]}: {auth_header[1]}",
            f"}}",
        ]

    if has_body:
        body = build_sample_body(operation, spec)
        # Bruno's body:json block IS the JSON object — include outer braces as-is
        body_str = json.dumps(body, indent=2)
        lines.append("")
        lines.append(f"body:json {body_str}")

    # Add path params
    path_params = [p for p in operation.get("parameters", []) if p.get("in") == "path"]
    if path_params:
        lines += [f"", f"params:path {{"]
        for p in path_params:
            schema_type = p.get("schema", {}).get("type", "")
            placeholder = "00000000-0000-0000-0000-000000000000" if "uuid" in p.get("schema", {}).get("format", "") or "id" in p["name"].lower() else f"your-{p['name']}-here"
            lines.append(f"  {p['name']}: {placeholder}")
        lines.append(f"}}")

    # Add query params
    query_params = [p for p in operation.get("parameters", []) if p.get("in") == "query"]
    if query_params:
        lines += [f"", f"query {{"]
        for p in query_params:
            default = p.get("schema", {}).get("default", "")
            lines.append(f"  {p['name']}: {default}")
        lines.append(f"}}")

    return "\n".join(lines) + "\n"


def build_sample_body(operation: dict, spec: dict) -> dict:
    """Build a sample request body from the OpenAPI schema."""
    body = operation.get("requestBody", {})
    content = body.get("content", {}).get("application/json", {})
    schema_ref = content.get("schema", {})

    schema = resolve_ref(schema_ref, spec)
    return sample_from_schema(schema, spec)


def resolve_ref(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        parts = schema["$ref"].lstrip("#/").split("/")
        result = spec
        for part in parts:
            result = result[part]
        return result
    return schema


def sample_from_schema(schema: dict, spec: dict) -> dict | list | str | int | bool | None:
    schema = resolve_ref(schema, spec)
    typ = schema.get("type")

    if typ == "object" or "properties" in schema:
        result = {}
        for key, val in schema.get("properties", {}).items():
            result[key] = sample_from_schema(val, spec)
        return result
    elif typ == "array":
        return []
    elif typ == "string":
        return schema.get("example") or schema.get("default") or ""
    elif typ == "integer":
        return schema.get("example") or schema.get("default") or 0
    elif typ == "boolean":
        return schema.get("default", False)
    elif typ == "number":
        return schema.get("default", 0.0)
    return None


ENV_TEMPLATE = """\
name: {name}
variables:
  - name: baseUrl
    value: http://localhost:8000
    enabled: true
    secret: false
  - name: adminSecret
    value: ""
    enabled: true
    secret: true
  - name: apiKey
    value: ""
    enabled: true
    secret: true
"""


def ensure_dev_env():
    dev_yml = ENVIRONMENTS_DIR / "dev.yml"
    if not dev_yml.exists():
        ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)
        dev_yml.write_text(ENV_TEMPLATE.format(name="dev"))
        print(f"  Created {dev_yml} — fill in your secrets")


def clear_bru_files():
    """Delete all .bru files and subdirectories except environments/."""
    for item in BRUNO_DIR.iterdir():
        if item == ENVIRONMENTS_DIR:
            continue
        if item.name == "bruno.json":
            continue
        if item.suffix == ".bru":
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def write_bru(folder: str, filename: str, content: str):
    if folder:
        target_dir = BRUNO_DIR / folder
    else:
        target_dir = BRUNO_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_text(content)


def main():
    print(f"Fetching OpenAPI spec from {OPENAPI_URL}...")
    spec = fetch_openapi()

    ensure_dev_env()
    print("Clearing existing .bru files...")
    clear_bru_files()

    paths = spec.get("paths", {})
    count = 0

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue

            folder = path_to_folder(path)
            name = operation.get("summary") or f"{method.upper()} {path}"
            filename = slugify(name) + ".bru"

            content = build_bru(method, path, operation, spec)
            write_bru(folder, filename, content)
            print(f"  {method.upper()} {path} → {folder}/{filename}")
            count += 1

    print(f"\nDone. {count} requests written to {BRUNO_DIR}/")


if __name__ == "__main__":
    main()
