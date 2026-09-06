"""Seal the reviewed catalog blocker, with exact Git-byte and prior-tag bindings."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pflow.release import REPO, REPO_ID, api, current_commit, publish, verify_release
from pflow.source import canonical, sha

TAG = "run-1-historical-catalog-blocked-v0.4.0"
PRIOR = {
    "run-1-source-proof-blocked-v0.1.0": ("7c313b1e31f73cbba20465d0ed05d12b52a19bce", 383485962),
    "run-1-continuity-blocked-v0.2.0": ("2c0062d90f6839516859368542ba3167cc41eadc", 383513515),
    "run-1-observed-catalog-blocked-v0.3.0": (
        "2a95c0d32344a413e17cca863d9dad6ac80474bf",
        383529513,
    ),
}


def main() -> None:
    commit = current_commit()
    if subprocess.check_output(["git", "status", "--porcelain"]):
        raise ValueError("clean committed checkpoint required")
    repository = json.loads(subprocess.check_output(["gh", "api", "repos/" + REPO]))
    if repository["id"] != REPO_ID or repository["full_name"] != REPO:
        raise ValueError("repository identity mismatch")
    if (
        not api("immutable-releases")["enabled"]
        or api("git/ref/heads/main")["object"]["sha"] != commit
    ):
        raise ValueError("remote commit/immutability mismatch")
    for tag, (old_commit, rid) in PRIOR.items():
        ref = api("git/ref/tags/" + tag)
        release = api("releases/" + str(rid))
        if (
            ref["object"]["type"] != "commit"
            or ref["object"]["sha"] != old_commit
            or not release["immutable"]
            or release["draft"]
            or release["tag_name"] != tag
        ):
            raise ValueError("prior checkpoint changed")
    runs = api("actions/workflows/check.yml/runs?per_page=20")["workflow_runs"]
    checks = next(
        (
            r
            for r in runs
            if r["head_sha"] == commit and r["event"] == "push" and r["head_branch"] == "main"
        ),
        None,
    )
    if checks is None or checks["status"] != "completed":
        print(
            canonical(
                dict(
                    ready=False,
                    reason="final_commit_CI_pending",
                    run_id=checks["id"] if checks else None,
                )
            ).decode()
        )
        return
    if checks["conclusion"] != "success":
        raise ValueError("final commit CI failed")
    names = (
        "observed-profile-policy-v1.json",
        "observed-profile-v1.md",
        "historical-catalog-capability-gap.md",
        "catalog-authority-review.md",
        "catalog-implementation-review.md",
        "catalog-evidence-inventory.json",
        "catalog-status.json",
        "catalog-consumer-handoff.json",
        "catalog-independent-result.json",
    )
    payloads = {
        name: subprocess.check_output(["git", "show", commit + ":docs/" + name]) for name in names
    }
    status = json.loads(payloads["catalog-status.json"])
    handoff = json.loads(payloads["catalog-consumer-handoff.json"])
    review = json.loads(payloads["catalog-independent-result.json"])
    review_raw = payloads["catalog-independent-result.json"]
    for document in (status, handoff):
        if document["independent_review"]["sha256"] != sha(review_raw):
            raise ValueError("stale independent-review pointer")
    review_release = api("releases/" + str(status["independent_review"]["release_id"]))
    if len(review_release["assets"]) != 1:
        raise ValueError("independent review inventory mismatch")
    verify_release(review_release, {review_release["assets"][0]["name"]: review_raw})
    if review_release["tag_name"] != handoff["independent_review"]["tag"]:
        raise ValueError("independent review locator mismatch")
    if (
        any(d["research_import_allowed"] is not False for d in (status, handoff, review))
        or status["certified_days"]
        or handoff["included_certified_utc_days"]
        or status["current_window_generation"] is not None
        or status["accumulation_running"]
        or status["scheduled_accumulation"]
    ):
        raise ValueError("blocker checkpoint cannot carry research authority")
    for contract in handoff["policy_contracts"]:
        raw = payloads[Path(contract["path"]).name]
        if sha(raw) != contract["sha256"] or len(raw) != contract["bytes"]:
            raise ValueError("frozen observed policy changed")
    manifest: dict[str, Any] = dict(
        schema="pendulumflow-historical-catalog-blocked-checkpoint.v1",
        repository=REPO,
        repository_id=REPO_ID,
        commit=commit,
        tag=TAG,
        semantic_profile="PENDULUMFLOW_V3_OBSERVED",
        semantic_profile_version=1,
        verdict=status["verdict"],
        research_import_allowed=False,
        certified_days=[],
        current_window_generation=None,
        accumulation_running=False,
        scheduled_accumulation=False,
        continuity_between_observations_certified=False,
        preserved_checkpoints=[dict(tag=t, commit=v[0], release_id=v[1]) for t, v in PRIOR.items()],
        continuation_condition=status["source_gap_condition"],
        validation_run={k: checks[k] for k in ("id", "head_sha", "conclusion", "html_url")},
        assets=[
            dict(logical_name=n, sha256=sha(v), bytes=len(v)) for n, v in sorted(payloads.items())
        ],
    )
    payloads["checkpoint-manifest.json"] = canonical(manifest)
    release = publish(
        TAG, payloads, commit, "Run 1: historical expected-listing authority unproven (v0.4.0)"
    )
    ref = api("git/ref/tags/" + TAG)
    if ref["object"]["type"] != "commit" or ref["object"]["sha"] != commit:
        raise ValueError("sealed checkpoint tag mismatch")
    result = dict(
        release_id=release["id"],
        tag=TAG,
        commit=commit,
        immutable=release["immutable"],
        manifest_sha256=sha(payloads["checkpoint-manifest.json"]),
        assets=[{k: a[k] for k in ("id", "name", "size", "digest")} for a in release["assets"]],
        check_run_id=checks["id"],
        verified_all_asset_bytes_before_and_after_seal=True,
        research_import_allowed=False,
    )
    Path("work/catalog-checkpoint-verified.json").write_bytes(canonical(result))
    print(canonical(result).decode())


if __name__ == "__main__":
    main()
