"""Independently verify a pinned catalog diagnostic; never approve research import."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
from typing import Any

from pflow.catalog_access import SCHEMA as ACCESS_SCHEMA
from pflow.catalog_access import validate_report as validate_access
from pflow.catalog_enumerate import ENUM_SCHEMA
from pflow.catalog_enumerate import summary as enumeration_summary
from pflow.catalog_enumerate import validate as validate_enumeration
from pflow.catalog_probe import SCHEMA as SCOUT_SCHEMA
from pflow.catalog_probe import validate_report as validate_scout
from pflow.release import api, read_asset, verify_release
from pflow.source import canonical, sha


def verify(tag: str, digest: str) -> dict[str, Any]:
    if not re.fullmatch(r"catalog-(probe|access|enumeration)-[0-9a-f]{64}", tag):
        raise ValueError("exact catalog diagnostic tag required")
    if not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("independent SHA-256 pin required")
    release = api("releases/tags/" + tag)
    enumeration = tag.startswith("catalog-enumeration-")
    if release is None or len(release["assets"]) != (2 if enumeration else 1):
        raise ValueError("exact report asset inventory required")
    suffix = (
        "--catalog-stream.json"
        if enumeration
        else (
            "--access-report.json" if tag.startswith("catalog-access-") else "--catalog-report.json"
        )
    )
    matches = [a for a in release["assets"] if a["name"].endswith(suffix)]
    if len(matches) != 1:
        raise ValueError("unique report required")
    asset = matches[0]
    if asset["size"] > 8_000_000 and not (
        platform.system() == "Linux" and os.environ.get("GITHUB_ACTIONS") == "true"
    ):
        raise ValueError("diagnostic exceeds small control-metadata limit")
    data = read_asset(asset)
    if sha(data) != digest:
        raise ValueError("independent report pin mismatch")
    expected = {asset["name"]: data}
    report = json.loads(data)
    if report["schema"] == SCOUT_SCHEMA and tag == "catalog-probe-" + report["identity"]:
        validate_scout(report, report["identity"])
    elif report["schema"] == ACCESS_SCHEMA and tag == "catalog-access-" + report["identity"]:
        validate_access(report)
    elif report["schema"] == ENUM_SCHEMA and tag == "catalog-enumeration-" + report["identity"]:
        validate_enumeration(report, report["specification"], report["commit"])
        overview = canonical(enumeration_summary(report))
        expected[sha(overview) + "--summary.json"] = overview
    else:
        raise ValueError("report/tag/schema mismatch")
    verify_release(release, expected)
    ref = api("git/ref/tags/" + tag)
    if ref["object"] != {"type": "commit", "sha": report["commit"], "url": ref["object"]["url"]}:
        raise ValueError("diagnostic immutable tag/transform mismatch")
    return {
        "release_id": release["id"],
        "asset_id": asset["id"],
        "tag": tag,
        "sha256": digest,
        "bytes": len(data),
        "commit": report["commit"],
        "requests": len(report.get("evidence", report)["requests"]),
        "downloaded_bytes": report.get("evidence", report)["downloaded_bytes"],
        "research_import_allowed": False,
        "expected_catalog_certified": False,
        "scope": "verified access/capability evidence only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha256", required=True)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.tag, arguments.sha256), sort_keys=True))
