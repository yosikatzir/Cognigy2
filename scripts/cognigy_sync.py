#!/usr/bin/env python3
"""Download and upload Cognigy project assets with automatic backups."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
ELEMENTS_DIR = ROOT / "elements"
SNAPSHOTS_DIR = ROOT / "snapshots"


@dataclass(frozen=True)
class ResourceConfig:
    folder: str
    get_path: str
    put_path: str


RESOURCE_MAP: dict[str, ResourceConfig] = {
    "project_metadata": ResourceConfig("project_metadata", "/v2.0/projects/{project_id}", "/v2.0/projects/{project_id}"),
    "ai_agents": ResourceConfig("ai_agents", "/v2.0/projects/{project_id}/agents", "/v2.0/projects/{project_id}/agents"),
    "flows": ResourceConfig("flows", "/v2.0/projects/{project_id}/flows", "/v2.0/projects/{project_id}/flows"),
    "flow_charts": ResourceConfig("flow_charts", "/v2.0/projects/{project_id}/flowcharts", "/v2.0/projects/{project_id}/flowcharts"),
    "intents": ResourceConfig("intents", "/v2.0/projects/{project_id}/intents", "/v2.0/projects/{project_id}/intents"),
    "example_sentences": ResourceConfig(
        "example_sentences",
        "/v2.0/projects/{project_id}/example-sentences",
        "/v2.0/projects/{project_id}/example-sentences",
    ),
    "endpoints": ResourceConfig("endpoints", "/v2.0/projects/{project_id}/endpoints", "/v2.0/projects/{project_id}/endpoints"),
    "lexicons": ResourceConfig("lexicons", "/v2.0/projects/{project_id}/lexicons", "/v2.0/projects/{project_id}/lexicons"),
}


class CognigyClient:
    def __init__(self, base_url: str, api_key: str, project_id: str, timeout_seconds: int = 60):
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_url(self, path: str) -> str:
        project_path = path.format(project_id=self.project_id)
        return f"{self.base_url}{project_path}"

    def _request(self, method: str, url: str, payload: Any | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
                if not body:
                    return {"status": "ok"}
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {err.code} for {url}: {detail}") from err

    def get_resource(self, resource_key: str) -> Any:
        cfg = RESOURCE_MAP[resource_key]
        return self._request("GET", self._build_url(cfg.get_path))

    def put_resource(self, resource_key: str, payload: Any) -> Any:
        cfg = RESOURCE_MAP[resource_key]
        return self._request("PUT", self._build_url(cfg.put_path), payload=payload)


def ensure_layout() -> None:
    for cfg in RESOURCE_MAP.values():
        (ELEMENTS_DIR / cfg.folder).mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def download_all(client: CognigyClient, destination_root: Path) -> None:
    for resource_key, cfg in RESOURCE_MAP.items():
        payload = client.get_resource(resource_key)
        out_file = destination_root / cfg.folder / f"{resource_key}.json"
        write_json(out_file, payload)
        print(f"Downloaded {resource_key} -> {out_file}")


def backup_before_upload(client: CognigyClient) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = SNAPSHOTS_DIR / timestamp
    print(f"Creating backup snapshot at {backup_dir}")
    download_all(client, backup_dir)
    return backup_dir


def upload_all(client: CognigyClient, source_root: Path) -> None:
    for resource_key, cfg in RESOURCE_MAP.items():
        src_file = source_root / cfg.folder / f"{resource_key}.json"
        if not src_file.exists():
            print(f"Skipping {resource_key}; file not found at {src_file}")
            continue
        payload = read_json(src_file)
        client.put_resource(resource_key, payload)
        print(f"Uploaded {resource_key} from {src_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cognigy repository sync utility")
    parser.add_argument("command", choices=["download", "upload", "backup"], help="Operation to run")
    parser.add_argument(
        "--source",
        default=str(ELEMENTS_DIR),
        help="Source root for upload (default: elements/)",
    )
    parser.add_argument(
        "--destination",
        default=str(ELEMENTS_DIR),
        help="Destination root for download (default: elements/)",
    )
    return parser.parse_args()


def make_client_from_env() -> CognigyClient:
    load_simple_dotenv(ROOT / ".env")
    base_url = os.getenv("COGNIGY_BASE_URL")
    api_key = os.getenv("COGNIGY_API_KEY")
    project_id = os.getenv("COGNIGY_PROJECT_ID")
    timeout_seconds = int(os.getenv("COGNIGY_TIMEOUT_SECONDS", "60"))

    missing = [
        name
        for name, value in {
            "COGNIGY_BASE_URL": base_url,
            "COGNIGY_API_KEY": api_key,
            "COGNIGY_PROJECT_ID": project_id,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    return CognigyClient(base_url=base_url, api_key=api_key, project_id=project_id, timeout_seconds=timeout_seconds)


def load_simple_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    ensure_layout()
    args = parse_args()
    client = make_client_from_env()

    if args.command == "download":
        download_all(client, Path(args.destination))
    elif args.command == "backup":
        backup_before_upload(client)
    elif args.command == "upload":
        backup_dir = backup_before_upload(client)
        print(f"Backup completed at {backup_dir}")
        upload_all(client, Path(args.source))


if __name__ == "__main__":
    main()
