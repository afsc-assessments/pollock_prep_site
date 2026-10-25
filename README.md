# Public pollock assessment methods

This repository is a generated publication. **Edit in the canonical [pollock_prep source (restricted)](https://github.com/noaa-afsc/pollock_prep); do not hand-edit these generated pages.**

- Public reading copy: https://afsc-assessments.github.io/pollock_prep_site/
- Canonical commit: `fabdfd3b4a688be161ec413861140f2664fd0e94`
- Build time (UTC): 2026-10-25T23:07:06Z
- Scope: methodological workflow and reviewed aggregate incremental-model execution account.
- Where things live and reproducible update flow: https://afsc-assessments.github.io/pollock_prep_site/where-things-live.html

`docs/` is the single published output tree. `release.json` records source selections and versions; `inventory.json` records exact output hashes. `tools/public_release.py` is an automatically copied validator from the canonical source. There are no parallel editable Quarto sources, scientific data downloads or private Git history here. The deployment workflow validates the release before publishing `docs/` with GitHub Pages. Organization access defaults are retained; this repository stores no source-access or cross-repository publishing credentials.

To update, review selected text in the canonical source, run its tests, commit, and run `python3 scripts/build_public_wiki.py --output-dir /tmp/pollock-public-release-NEW`. Validate with `python3 scripts/public_release.py /tmp/pollock-public-release-NEW`, then publish that exact generated directory with existing authorized account access. See the canonical `public/README.md` for the manual Git procedure and stale-file checks.
