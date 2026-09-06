"""Verify an explicitly pinned immutable generation without any mutable current ref."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pflow.model import validate_quote
from pflow.release import api, read_asset, verify_release
from pflow.source import canonical, sha


def verify(tag: str, digest: str, evidence_only: bool = False) -> dict[str, Any]:
    if not re.fullmatch(r"source-probe-[0-9a-f]{64}", tag):
        raise ValueError("an exact content-addressed source-proof generation is required")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("an independently supplied report SHA-256 pin is required")
    release = api(f"releases/tags/{tag}")
    if release is None:
        raise ValueError("pinned generation unavailable")
    verify_release(release)
    if len(release["assets"]) != 1:
        raise ValueError("unexpected pinned inventory")
    asset = release["assets"][0]
    if asset["name"] != digest + "--report.json":
        raise ValueError("pinned content address differs")
    payload = read_asset(asset)
    if sha(payload) != digest:
        raise ValueError("consumer pin mismatch")
    report = json.loads(payload)
    if report["partition_identity"] != tag.removeprefix("source-probe-"):
        raise ValueError("partition/tag mismatch")
    if report["schema"] != "pendulumflow-source-canary.v1":
        raise ValueError("unsupported evidence contract")
    for row in report["quote_samples"].values():
        validate_quote(row)
    if report["research_authority"] is not False or report["certified_days"]:
        raise ValueError("source canary cannot promote days")
    if not evidence_only:
        raise ValueError("NO_RESEARCH_AUTHORITY: source-proof only; research import blocked")
    return {
        "verified": True,
        "research_import_allowed": False,
        "release_id": release["id"],
        "asset_id": asset["id"],
        "tag": tag,
        "sha256": digest,
        "immutable": release["immutable"],
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--evidence-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.tag, args.sha256, args.evidence_only)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(result))
    print(canonical({key: value for key, value in result.items() if key != "report"}).decode())


if __name__ == "__main__":
    main()
