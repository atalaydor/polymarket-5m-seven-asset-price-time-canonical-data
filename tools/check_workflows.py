"""Bounded structural workflow checks, in addition to actionlint in CI."""

import re
from pathlib import Path
from typing import Any

import yaml


def main() -> None:
    for path in Path(".github/workflows").glob("*.yml"):
        data: dict[str, Any] = yaml.safe_load(path.read_text())
        assert "jobs" in data
        for job in data["jobs"].values():
            assert job["runs-on"] == "ubuntu-24.04"
            assert 1 <= job["timeout-minutes"] <= 45
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
        print(f"{path}: standard Linux, bounded jobs, pinned Actions")


if __name__ == "__main__":
    main()
