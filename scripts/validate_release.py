#!/usr/bin/env python3
"""Validate immutable whitepaper releases and the current release pointer."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_PDF_BYTES = 100 * 1024 * 1024
CURRENT_FIELDS = {"version"}
RELEASE_FIELDS = {
    "title",
    "version",
    "displayVersion",
    "releaseDate",
    "file",
    "description",
    "sha256",
}


class ReleaseValidationError(ValueError):
    """Raised when repository release data is invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseValidationError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseValidationError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseValidationError(f"Expected a JSON object in {path}")
    return value


def _require_exact_fields(value: dict[str, Any], expected: set[str], path: Path) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ReleaseValidationError(
            f"Unexpected fields in {path}; missing={missing}, extra={extra}"
        )


def _require_nonempty_string(value: dict[str, Any], field: str, path: Path) -> str:
    field_value = value.get(field)
    if not isinstance(field_value, str) or not field_value.strip():
        raise ReleaseValidationError(f"{field} must be a non-empty string in {path}")
    return field_value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pdf(path: Path, expected_sha256: str) -> None:
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise ReleaseValidationError(f"Release PDF does not exist: {path}") from exc
    if size == 0:
        raise ReleaseValidationError(f"Release PDF is empty: {path}")
    if size >= MAX_PDF_BYTES:
        raise ReleaseValidationError(
            f"Release PDF must be smaller than 100 MiB: {path} ({size} bytes)"
        )
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ReleaseValidationError(f"Release file has no PDF signature: {path}")
    if not data.rstrip().endswith(b"%%EOF"):
        raise ReleaseValidationError(f"Release PDF has no final %%EOF marker: {path}")
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise ReleaseValidationError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, got {actual_sha256}"
        )


def validate_release_metadata(root: Path, metadata_path: Path) -> dict[str, Any]:
    root = root.resolve()
    releases_dir = (root / "releases").resolve()
    metadata_path = metadata_path.resolve()
    metadata = _load_json(metadata_path)
    _require_exact_fields(metadata, RELEASE_FIELDS, metadata_path)

    version = _require_nonempty_string(metadata, "version", metadata_path)
    if not SEMVER_RE.fullmatch(version):
        raise ReleaseValidationError(
            f"version must be strict MAJOR.MINOR.PATCH SemVer in {metadata_path}"
        )

    display_version = _require_nonempty_string(metadata, "displayVersion", metadata_path)
    if not re.fullmatch(r"\d+(?:\.\d+){1,2}", display_version):
        raise ReleaseValidationError(f"Invalid displayVersion in {metadata_path}")

    release_date = _require_nonempty_string(metadata, "releaseDate", metadata_path)
    try:
        parsed_date = date.fromisoformat(release_date)
    except ValueError as exc:
        raise ReleaseValidationError(
            f"releaseDate must be a real ISO date in {metadata_path}"
        ) from exc
    if parsed_date.isoformat() != release_date:
        raise ReleaseValidationError(f"releaseDate must use YYYY-MM-DD in {metadata_path}")

    _require_nonempty_string(metadata, "title", metadata_path)
    _require_nonempty_string(metadata, "description", metadata_path)
    expected_sha256 = _require_nonempty_string(metadata, "sha256", metadata_path)
    if not SHA256_RE.fullmatch(expected_sha256):
        raise ReleaseValidationError(f"sha256 must be 64 lowercase hex characters in {metadata_path}")

    expected_pdf_relative = f"releases/neurolab-whitepaper-v{version}.pdf"
    file_value = _require_nonempty_string(metadata, "file", metadata_path)
    if file_value != expected_pdf_relative:
        raise ReleaseValidationError(
            f"file must be exactly {expected_pdf_relative} in {metadata_path}"
        )

    expected_metadata_path = releases_dir / f"neurolab-whitepaper-v{version}.json"
    if metadata_path != expected_metadata_path:
        raise ReleaseValidationError(
            f"Release metadata filename must be {expected_metadata_path.name}"
        )

    pdf_path = (root / file_value).resolve()
    if pdf_path.parent != releases_dir:
        raise ReleaseValidationError(f"Release PDF must remain directly under {releases_dir}")
    _validate_pdf(pdf_path, expected_sha256)
    return metadata


def validate_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    releases_dir = root / "releases"
    current_path = root / "current-release.json"
    current = _load_json(current_path)
    _require_exact_fields(current, CURRENT_FIELDS, current_path)
    current_version = _require_nonempty_string(current, "version", current_path)
    if not SEMVER_RE.fullmatch(current_version):
        raise ReleaseValidationError(
            f"Current version must be strict MAJOR.MINOR.PATCH SemVer in {current_path}"
        )

    if not releases_dir.is_dir():
        raise ReleaseValidationError(f"Missing releases directory: {releases_dir}")

    metadata_paths = sorted(releases_dir.glob("neurolab-whitepaper-v*.json"))
    pdf_paths = sorted(releases_dir.glob("neurolab-whitepaper-v*.pdf"))
    unexpected = sorted(
        path for path in releases_dir.iterdir()
        if path.is_file() and path not in metadata_paths and path not in pdf_paths
    )
    if unexpected:
        raise ReleaseValidationError(
            "Unexpected files in releases/: " + ", ".join(path.name for path in unexpected)
        )
    if not metadata_paths:
        raise ReleaseValidationError("No release metadata files were found")

    releases: dict[str, dict[str, Any]] = {}
    for metadata_path in metadata_paths:
        metadata = validate_release_metadata(root, metadata_path)
        version = metadata["version"]
        if version in releases:
            raise ReleaseValidationError(f"Duplicate release version: {version}")
        releases[version] = metadata

    expected_pdfs = {(root / metadata["file"]).resolve() for metadata in releases.values()}
    actual_pdfs = {path.resolve() for path in pdf_paths}
    if actual_pdfs != expected_pdfs:
        missing = sorted(str(path) for path in expected_pdfs - actual_pdfs)
        orphaned = sorted(str(path) for path in actual_pdfs - expected_pdfs)
        raise ReleaseValidationError(
            f"Release PDF/metadata mismatch; missing={missing}, orphaned={orphaned}"
        )

    if current_version not in releases:
        raise ReleaseValidationError(
            f"current-release.json points to missing release {current_version}"
        )
    return releases[current_version]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()
    try:
        current = validate_repository(args.root)
    except ReleaseValidationError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        "Validated whitepaper release "
        f"{current['version']} (display {current['displayVersion']}) at {current['file']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
