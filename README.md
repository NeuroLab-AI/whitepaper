# NeuroLab Whitepaper

This repository publishes the public NeuroLab whitepaper through GitHub Pages.

- Permanent landing page: <https://neurolab-ai.github.io/whitepaper/>
- Stable current-PDF URL: <https://neurolab-ai.github.io/whitepaper/neurolab-whitepaper.pdf>
- Current release metadata: <https://neurolab-ai.github.io/whitepaper/current-release.json>

## Current release

The initial public review draft is release `0.11.0` and displays document version `0.11`, matching the version printed inside the PDF.

`current-release.json` identifies the currently published release. Each version has an immutable PDF and adjacent immutable JSON metadata file under `releases/`.

## Local validation and preview

Python 3.12 or newer is recommended. The scripts use only the Python standard library.

```shell
python -m unittest discover -s tests -v
python scripts/validate_release.py
python scripts/build_site.py
python -m http.server 8000 --directory _site
```

Open <http://localhost:8000/> after starting the preview server.

## Publishing a release

1. Export the approved PDF with the intended display version printed inside it.
2. Add it as `releases/neurolab-whitepaper-vMAJOR.MINOR.PATCH.pdf`.
3. Add adjacent JSON metadata with the same filename stem.
4. Record the PDF's SHA-256 checksum in the metadata.
5. Update `current-release.json` to the new semantic version.
6. Open a pull request and allow the validation workflow to finish.
7. Merge after approval. The Pages workflow validates, builds, and deploys automatically.

Existing files under `releases/` must never be edited, renamed, or deleted. Corrections require a new version.

## Rollback

To roll back, change only `current-release.json` to a previously published semantic version and merge the change through a pull request. The historical PDF and its metadata already remain in the archive.

## Site generation

The generated `_site/` directory is intentionally untracked. `scripts/build_site.py` creates it from the release archive and site template, publishes every archived release, copies the current release to the stable `neurolab-whitepaper.pdf` alias, and writes a public current-release manifest.
