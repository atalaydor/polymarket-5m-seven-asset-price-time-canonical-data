"""Independent exact-pin verifier for continuity diagnostics, never research import."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pflow.continuity_probe import HOURS, MANIFEST_PINS, PRIOR_SHA, validate_report
from pflow.release import api, read_asset, verify_release
from pflow.source import canonical, sha


def verify(tag: str, digest: str) -> dict[str, Any]:
    if not re.fullmatch("continuity-probe-[0-9a-f]{64}", tag):
        raise ValueError("exact diagnostic generation required")
    if not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("independent SHA-256 pin required")
    release = api("releases/tags/" + tag)
    if release is None:
        raise ValueError("pinned release inaccessible or absent")
    verify_release(release)
    if len(release["assets"]) != 1:
        raise ValueError("unexpected diagnostic inventory")
    asset = release["assets"][0]
    if asset["name"] != digest + "--diagnostic.json":
        raise ValueError("unexpected diagnostic asset pin")
    data = read_asset(asset)
    if sha(data) != digest:
        raise ValueError("independent diagnostic pin mismatch")
    report = json.loads(data)
    validate_report(report)
    identity = sha(
        canonical(
            {
                "commit": report["commit"],
                "hours": HOURS,
                "manifests": MANIFEST_PINS,
                "prior": PRIOR_SHA,
            }
        )
    )
    if report["identity"] != identity or tag != "continuity-probe-" + identity:
        raise ValueError("diagnostic transform/source identity mismatch")
    return {
        "verified": True,
        "research_import_allowed": False,
        "immutable": True,
        "tag": tag,
        "sha256": digest,
        "release_id": release["id"],
        "asset_id": asset["id"],
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.tag, args.sha256)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(result))
    print(canonical({k: v for k, v in result.items() if k != "report"}).decode())


if __name__ == "__main__":
    main()
