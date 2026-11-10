# Releasing SciQLop

A release can go out in two steps: release candidates first, for users who opted in, then the release.
Candidates are optional. A patch release can skip them.

## How users get candidates

Users opt in with **Settings → Workspaces → SciQLop version → "Latest release candidate"**. Then:

- the welcome page offers to update a workspace to the newest candidate;
- new workspaces start on it;
- the workspace version picker lists candidates, marked "(release candidate)".

They only see candidates newer than the latest release. Once `0.15.0` is out, its candidates disappear,
and opted-in users are offered `0.15.0` like everyone else.

Each workspace has its own SciQLop version, so a tester can keep one workspace on the release and
another on the candidate. Nobody needs a new installer, as long as the candidate runs under theirs
(see `[tool.sciqlop.launcher] minimum` in `pyproject.toml`).

## Cutting a candidate

1. Rename `## Unreleased` in `CHANGELOG.md` to `## v0.15.0rc1 — <date>`.
   Later candidates add their own sections above it.
2. Set the version:
   ```
   uvx bump-my-version bump --new-version 0.15.0rc1    # the first candidate
   uvx bump-my-version bump build                      # rc1 -> rc2, for the next ones
   ```
   This commits. Write the version exactly as PEP 440 normalises it (`0.15.0rc1`, not `0.15.0-rc1`
   or `0.15.0.rc1`): the welcome page reads `pyproject.toml` from the tag `v<version as PyPI lists it>`
   to check that the installer can run it.
3. Tag and push:
   ```
   git tag -a v0.15.0rc1 -m "Release candidate v0.15.0rc1"
   git push origin main v0.15.0rc1
   ```
4. On GitHub, create a release from the tag and tick **"Set as a pre-release"**.
   Publishing it uploads the package to PyPI (`pythonpublish.yml`) and builds the installers
   (`SingleExe.yml`), as for a release. The installer download link
   (`releases/latest`) skips pre-releases, so other users are not pointed at it.
5. Tell the testers. Plugin authors who need the new API should declare `sciqlop>=0.15.0rc1`,
   not `sciqlop>=0.15`: PEP 440 ranks `0.15.0rc1` below `0.15.0`, so `>=0.15` doesn't install next to
   a candidate. SciQLop's own plugin compatibility check treats `0.15.0rc1` as `0.15.0` either way.

Between candidates, only fixes go in.

## Releasing

1. Merge the candidates' changelog sections into `## v0.15.0 — <date>`.
2. Set the version:
   ```
   uvx bump-my-version bump release                    # after candidates: rc2 -> 0.15.0
   uvx bump-my-version bump --new-version 0.15.1       # without candidates (bump release from .devN gives rc0)
   ```
3. If the installer changed (`scripts/launcher.version`, Python version), set
   `[tool.sciqlop.launcher] minimum` to the version being released. `tests/test_launcher_compat.py`
   fails when they drift.
4. Tag `v0.15.0`, push, and create the GitHub release, **not** marked pre-release.
5. Start the next cycle: `uvx bump-my-version bump patch` (or `minor`) → `0.15.1.dev0`.
