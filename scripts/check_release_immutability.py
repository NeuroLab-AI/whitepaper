#!/usr/bin/env python3
"""Reject changes to previously committed immutable release files."""

from __future__ import annotations

import argparse
import subprocess


def changed_release_entries(base_ref: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            f"{base_ref}...HEAD",
            "--",
            "releases",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    violations: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status = line.split("\t", 1)[0]
        if status != "A":
            violations.append(line)
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args()
    try:
        violations = changed_release_entries(args.base_ref)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc))
        return 1
    if violations:
        print("ERROR: Existing release files are immutable:")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("Release archive immutability check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
