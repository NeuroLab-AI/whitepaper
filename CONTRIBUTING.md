# Contributing

Changes to the public whitepaper are reviewed through pull requests.

## Release rules

- Use strict `MAJOR.MINOR.PATCH` semantic versions for release identifiers.
- The document may use a shorter `displayVersion` when required to match text already printed in the PDF.
- Add a new PDF and adjacent metadata file for every release.
- Never modify, rename, or delete an existing file under `releases/`.
- Keep the PDF filename, metadata filename, semantic version, checksum, and manifest pointer consistent.
- Use the date on which that respective version is first made public.
- Keep version-specific descriptions with their respective immutable metadata files.

## Before opening a pull request

Run:

```shell
python -m unittest discover -s tests -v
python scripts/validate_release.py
python scripts/build_site.py
```

Inspect `_site/index.html`, confirm that the versioned PDF and stable alias open, and verify that relative links work from the `/whitepaper/` project-site path.

Pull requests that change a previously published release will fail the archive immutability check.
