"""Native immutable evidence publication, never a certification shortcut."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from pflow.source import canonical, sha

REPO = "atalaydor/polymarket-5m-seven-asset-price-time-canonical-data"
REPO_ID = 1358712762


def api(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    command = [
        "gh",
        "api",
        "--method",
        method,
        "-H",
        "X-GitHub-Api-Version: 2026-03-10",
        f"repos/{REPO}/{path}",
    ]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command,
        input=canonical(body) if body is not None else None,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        if "HTTP 404" in result.stderr.decode():
            return None
        raise RuntimeError(result.stderr.decode())
    return json.loads(result.stdout) if result.stdout.strip() else None


def read_asset(asset: dict[str, Any], draft: bool = False) -> bytes:
    url = asset["browser_download_url"]
    expected_prefix = f"https://github.com/{REPO}/releases/download/"
    if not url.startswith(expected_prefix):
        raise ValueError("unexpected release asset origin")
    if draft:
        # gh handles authenticated API redirects without exposing the token to
        # user output or forwarding it through our source HTTP reader.
        data = subprocess.check_output(
            [
                "gh",
                "api",
                "--method",
                "GET",
                "-H",
                "Accept: application/octet-stream",
                "-H",
                "X-GitHub-Api-Version: 2026-03-10",
                f"repos/{REPO}/releases/assets/{asset['id']}",
            ]
        )
    else:
        with urllib.request.urlopen(url, timeout=90) as response:
            data = bytes(response.read(asset["size"] + 1))
    if len(data) != asset["size"] or "sha256:" + sha(data) != asset["digest"]:
        raise ValueError("independent release bytes fail size/digest")
    return data


def verify_release(release: dict[str, Any], expected: dict[str, bytes] | None = None) -> None:
    if release["draft"] or release["prerelease"] or not release.get("immutable"):
        raise ValueError("native immutable final release required")
    assets = release["assets"]
    if not assets or len({asset["name"] for asset in assets}) != len(assets):
        raise ValueError("empty or duplicate inventory")
    if expected is not None and {asset["name"] for asset in assets} != expected.keys():
        raise ValueError("release inventory mismatch")
    for asset in assets:
        data = read_asset(asset)
        if asset["state"] != "uploaded" or sha(data) not in asset["name"]:
            raise ValueError("asset state or content address mismatch")
        if expected is not None and data != expected[asset["name"]]:
            raise ValueError("release differs from expected payload")


def publish(tag: str, payloads: dict[str, bytes], commit: str, title: str) -> dict[str, Any]:
    assets = {f"{sha(data)}--{name}": data for name, data in payloads.items()}
    if any(not data or len(data) >= 1_900_000_000 for data in assets.values()):
        raise ValueError("empty/oversized release asset")
    release = api(f"releases/tags/{tag}")
    if release is None:
        release = api(
            "releases",
            "POST",
            {
                "tag_name": tag,
                "target_commitish": commit,
                "name": title,
                "draft": True,
                "prerelease": False,
                "body": "Source-proof evidence only. No certified research authority.",
            },
        )
    if not release["draft"]:
        verify_release(release, assets)
        return dict(release)
    existing = {item["name"]: item for item in release["assets"]}
    if not existing.keys() <= assets.keys():
        raise ValueError("partial publication has unexpected assets; preserve and fail closed")
    with tempfile.TemporaryDirectory() as directory:
        for name, data in assets.items():
            if name in existing:
                item = existing[name]
                if item["size"] != len(data) or item.get("digest") != "sha256:" + sha(data):
                    raise ValueError("staged object differs; never overwrite")
                continue
            path = Path(directory) / name
            path.write_bytes(data)
            subprocess.run(["gh", "release", "upload", tag, str(path), "--repo", REPO], check=True)
    checked = api(f"releases/{release['id']}")
    actual = {item["name"]: item for item in checked["assets"]}
    if actual.keys() != assets.keys():
        raise ValueError("incomplete staging inventory")
    for name, data in assets.items():
        item = actual[name]
        if (
            item["state"] != "uploaded"
            or item["size"] != len(data)
            or item["digest"] != "sha256:" + sha(data)
        ):
            raise ValueError("staged size/digest disagreement")
        if read_asset(item, draft=True) != data:
            raise ValueError("independently read staged bytes differ before sealing")
    sealed = api(f"releases/{release['id']}", "PATCH", {"draft": False, "make_latest": "false"})
    # Native publication is atomic with respect to release sealing. Independent
    # read-after-write verifies the sealed bytes; no mutation follows this point.
    verify_release(sealed, assets)
    return dict(sealed)


def current_commit() -> str:
    return (
        os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )
