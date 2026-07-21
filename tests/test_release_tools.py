from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_site  # noqa: E402
import check_release_immutability  # noqa: E402
import validate_release  # noqa: E402


def write_valid_repository(root: Path) -> bytes:
    releases = root / "releases"
    site = root / "site"
    assets = site / "assets"
    releases.mkdir(parents=True)
    assets.mkdir(parents=True)
    pdf_data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    pdf_path = releases / "neurolab-whitepaper-v0.11.0.pdf"
    pdf_path.write_bytes(pdf_data)
    metadata = {
        "title": "Archived Whitepaper Title",
        "version": "0.11.0",
        "displayVersion": "0.11",
        "releaseDate": "2026-07-20",
        "file": "releases/neurolab-whitepaper-v0.11.0.pdf",
        "description": "Initial public review draft of the NeuroLab AI whitepaper.",
        "sha256": hashlib.sha256(pdf_data).hexdigest(),
    }
    (releases / "neurolab-whitepaper-v0.11.0.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    (root / "current-release.json").write_text(
        json.dumps({"version": "0.11.0"}), encoding="utf-8"
    )
    tokens = " ".join("{{" + token + "}}" for token in sorted(build_site.TOKENS))
    (site / "index.template.html").write_text(tokens, encoding="utf-8")
    (site / "styles.css").write_text("body {}", encoding="utf-8")
    (assets / "neurolab-wordmark.png").write_bytes(b"wordmark")
    return pdf_data


class ReleaseValidationTests(unittest.TestCase):
    def test_valid_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_valid_repository(root)
            current = validate_release.validate_repository(root)
            self.assertEqual(current["version"], "0.11.0")
            self.assertEqual(current["displayVersion"], "0.11")

    def test_invalid_checksum_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_valid_repository(root)
            metadata_path = root / "releases" / "neurolab-whitepaper-v0.11.0.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["sha256"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(
                validate_release.ReleaseValidationError, "SHA-256 mismatch"
            ):
                validate_release.validate_repository(root)

    def test_two_part_semver_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_valid_repository(root)
            (root / "current-release.json").write_text(
                json.dumps({"version": "0.11"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                validate_release.ReleaseValidationError, "MAJOR.MINOR.PATCH"
            ):
                validate_release.validate_repository(root)

    def test_path_outside_release_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_valid_repository(root)
            metadata_path = root / "releases" / "neurolab-whitepaper-v0.11.0.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["file"] = "../neurolab-whitepaper-v0.11.0.pdf"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(
                validate_release.ReleaseValidationError, "file must be exactly"
            ):
                validate_release.validate_repository(root)


class SiteBuildTests(unittest.TestCase):
    def test_build_copies_versioned_pdf_alias_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pdf_data = write_valid_repository(root)
            output = build_site.build(root)
            self.assertEqual((output / "neurolab-whitepaper.pdf").read_bytes(), pdf_data)
            self.assertEqual(
                (output / "releases" / "neurolab-whitepaper-v0.11.0.pdf").read_bytes(),
                pdf_data,
            )
            self.assertEqual(
                (output / "assets" / "neurolab-wordmark.png").read_bytes(),
                b"wordmark",
            )
            public_manifest = json.loads(
                (output / "current-release.json").read_text(encoding="utf-8")
            )
            self.assertEqual(public_manifest["title"], build_site.PUBLICATION_TITLE)
            self.assertEqual(public_manifest["stableAlias"], "neurolab-whitepaper.pdf")
            rendered_index = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn(build_site.PUBLICATION_TITLE, rendered_index)
            self.assertIn(hashlib.sha256(b"body {}").hexdigest()[:12], rendered_index)
            self.assertNotIn("{{", rendered_index)


class ReleaseImmutabilityTests(unittest.TestCase):
    @patch("check_release_immutability.subprocess.run")
    def test_new_release_files_are_allowed(self, run) -> None:
        run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "A\treleases/neurolab-whitepaper-v1.0.0.pdf\n"
                "A\treleases/neurolab-whitepaper-v1.0.0.json\n"
            ),
            stderr="",
        )
        self.assertEqual(
            check_release_immutability.changed_release_entries("origin/main"), []
        )

    @patch("check_release_immutability.subprocess.run")
    def test_changed_existing_release_is_rejected(self, run) -> None:
        changed = "M\treleases/neurolab-whitepaper-v0.11.0.pdf"
        run.return_value = CompletedProcess(
            args=[], returncode=0, stdout=changed + "\n", stderr=""
        )
        self.assertEqual(
            check_release_immutability.changed_release_entries("origin/main"),
            [changed],
        )


if __name__ == "__main__":
    unittest.main()
