#!/usr/bin/env python3
"""Build the static GitHub Pages artifact for the NeuroLabs whitepaper."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from datetime import date
from pathlib import Path

from validate_release import validate_repository


TOKENS = {
    "title",
    "description",
    "version",
    "display_version",
    "release_date",
    "pdf_path",
    "stable_pdf_path",
}


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key in TOKENS:
        token = "{{" + key + "}}"
        if token not in rendered:
            raise ValueError(f"Missing template token: {token}")
        rendered = rendered.replace(token, html.escape(values[key], quote=True))
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("Unresolved template token remains in generated index.html")
    return rendered


def build(root: Path) -> Path:
    root = root.resolve()
    current = validate_repository(root)
    output = (root / "_site").resolve()
    if output.parent != root or output.name != "_site":
        raise RuntimeError(f"Refusing to build into unsafe output path: {output}")
    if output.exists():
        shutil.rmtree(output)
    (output / "releases").mkdir(parents=True)

    template_path = root / "site" / "index.template.html"
    stylesheet_path = root / "site" / "styles.css"
    if not template_path.is_file() or not stylesheet_path.is_file():
        raise FileNotFoundError("Required site template or stylesheet is missing")

    for release_path in sorted((root / "releases").glob("neurolab-whitepaper-v*.*")):
        if release_path.suffix in {".pdf", ".json"}:
            shutil.copy2(release_path, output / "releases" / release_path.name)

    current_pdf = root / current["file"]
    stable_pdf_name = "neurolab-whitepaper.pdf"
    shutil.copy2(current_pdf, output / stable_pdf_name)
    shutil.copy2(stylesheet_path, output / "styles.css")

    release_date = date.fromisoformat(current["releaseDate"])
    values = {
        "title": current["title"],
        "description": current["description"],
        "version": current["version"],
        "display_version": current["displayVersion"],
        "release_date": release_date.strftime("%B %d, %Y"),
        "pdf_path": "./" + current["file"],
        "stable_pdf_path": "./" + stable_pdf_name,
    }
    rendered = _render_template(template_path.read_text(encoding="utf-8"), values)
    (output / "index.html").write_text(rendered, encoding="utf-8", newline="\n")

    public_manifest = dict(current)
    public_manifest["stableAlias"] = stable_pdf_name
    public_manifest["versionedUrl"] = current["file"]
    (output / "current-release.json").write_text(
        json.dumps(public_manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()
    output = build(args.root)
    print(f"Built GitHub Pages artifact at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
