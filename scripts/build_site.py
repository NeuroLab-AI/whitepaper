#!/usr/bin/env python3
"""Build the static GitHub Pages artifact for the NeuroLab whitepaper."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
from datetime import date
from pathlib import Path

from validate_release import validate_repository


TEXT_TOKENS = {
    "title",
    "description",
    "version",
    "display_version",
    "release_date",
    "pdf_path",
    "stable_pdf_path",
    "page_count",
    "cover_image_path",
    "abstract",
    "stylesheet_version",
}
RAW_TOKENS = {"contents_html"}
TOKENS = TEXT_TOKENS | RAW_TOKENS
PUBLICATION_TITLE = "NeuroLab Whitepaper"


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key in TEXT_TOKENS:
        token = "{{" + key + "}}"
        if token not in rendered:
            raise ValueError(f"Missing template token: {token}")
        rendered = rendered.replace(token, html.escape(values[key], quote=True))
    for key in RAW_TOKENS:
        token = "{{" + key + "}}"
        if token not in rendered:
            raise ValueError(f"Missing template token: {token}")
        rendered = rendered.replace(token, values[key])
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("Unresolved template token remains in generated index.html")
    return rendered


def _load_release_content(root: Path, version: str) -> tuple[dict, Path]:
    content_path = root / "site" / "release-content" / f"{version}.json"
    if not content_path.is_file():
        raise FileNotFoundError(
            f"Version-specific site content is missing for release {version}"
        )
    content = json.loads(content_path.read_text(encoding="utf-8"))
    if content.get("version") != version:
        raise ValueError("Version-specific site content does not match current release")
    page_count = content.get("pageCount")
    if not isinstance(page_count, int) or page_count < 1:
        raise ValueError("Release pageCount must be a positive integer")
    abstract = content.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        raise ValueError("Release abstract must be a non-empty string")
    cover_name = content.get("coverImage")
    if (
        not isinstance(cover_name, str)
        or Path(cover_name).name != cover_name
        or Path(cover_name).suffix.lower() != ".webp"
    ):
        raise ValueError("Release coverImage must be a WebP filename")
    cover_path = root / "site" / "assets" / cover_name
    if not cover_path.is_file():
        raise FileNotFoundError(f"Release cover image is missing: {cover_name}")
    contents = content.get("contents")
    if not isinstance(contents, list) or not contents:
        raise ValueError("Release contents must be a non-empty list")
    for entry in contents:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("title"), str)
            or not entry["title"].strip()
            or not isinstance(entry.get("page"), int)
            or not 1 <= entry["page"] <= page_count
        ):
            raise ValueError("Each contents entry requires a title and valid page")
    return content, cover_path


def _render_contents(contents: list[dict], pdf_path: str) -> str:
    items = []
    for index, entry in enumerate(contents, start=1):
        title = html.escape(entry["title"])
        page = entry["page"]
        href = html.escape(f"{pdf_path}#page={page}", quote=True)
        items.append(
            "          <li>\n"
            f'            <a href="{href}" target="_blank" rel="noopener">\n'
            f'              <span class="contents-index">{index:02d}</span>\n'
            f'              <span class="contents-title">{title}</span>\n'
            f'              <span class="contents-page">Page {page}</span>\n'
            "            </a>\n"
            "          </li>"
        )
    return "\n".join(items)


def build(root: Path) -> Path:
    root = root.resolve()
    current = validate_repository(root)
    output = (root / "_site").resolve()
    if output.parent != root or output.name != "_site":
        raise RuntimeError(f"Refusing to build into unsafe output path: {output}")
    if output.exists():
        shutil.rmtree(output)
    (output / "releases").mkdir(parents=True)
    (output / "assets").mkdir(parents=True)

    template_path = root / "site" / "index.template.html"
    stylesheet_path = root / "site" / "styles.css"
    wordmark_path = root / "site" / "assets" / "neurolab-wordmark.png"
    brain_art_path = root / "site" / "assets" / "neural-brain-hero.webp"
    if not all(
        path.is_file()
        for path in (template_path, stylesheet_path, wordmark_path, brain_art_path)
    ):
        raise FileNotFoundError(
            "Required site template, stylesheet, wordmark, or brain artwork is missing"
        )

    for release_path in sorted((root / "releases").glob("neurolab-whitepaper-v*.*")):
        if release_path.suffix in {".pdf", ".json"}:
            shutil.copy2(release_path, output / "releases" / release_path.name)

    current_pdf = root / current["file"]
    release_content, cover_path = _load_release_content(root, current["version"])
    stable_pdf_name = "neurolab-whitepaper.pdf"
    shutil.copy2(current_pdf, output / stable_pdf_name)
    shutil.copy2(stylesheet_path, output / "styles.css")
    shutil.copy2(wordmark_path, output / "assets" / wordmark_path.name)
    shutil.copy2(brain_art_path, output / "assets" / brain_art_path.name)
    shutil.copy2(cover_path, output / "assets" / cover_path.name)

    release_date = date.fromisoformat(current["releaseDate"])
    pdf_path = "./" + current["file"]
    values = {
        "title": PUBLICATION_TITLE,
        "description": current["description"],
        "version": current["version"],
        "display_version": current["displayVersion"],
        "release_date": release_date.strftime("%B %d, %Y"),
        "pdf_path": pdf_path,
        "stable_pdf_path": "./" + stable_pdf_name,
        "page_count": str(release_content["pageCount"]),
        "cover_image_path": "./assets/" + cover_path.name,
        "abstract": release_content["abstract"],
        "contents_html": _render_contents(release_content["contents"], pdf_path),
        "stylesheet_version": hashlib.sha256(stylesheet_path.read_bytes()).hexdigest()[:12],
    }
    rendered = _render_template(template_path.read_text(encoding="utf-8"), values)
    (output / "index.html").write_text(rendered, encoding="utf-8", newline="\n")

    public_manifest = dict(current)
    public_manifest["title"] = PUBLICATION_TITLE
    public_manifest["stableAlias"] = stable_pdf_name
    public_manifest["versionedUrl"] = current["file"]
    public_manifest["pageCount"] = release_content["pageCount"]
    public_manifest["coverImage"] = "assets/" + cover_path.name
    public_manifest["contents"] = release_content["contents"]
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
