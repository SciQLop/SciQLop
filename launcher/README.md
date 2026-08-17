# SciQLop launcher

A small, statically-linked C++ binary that prepares a workspace and starts
SciQLop. It ships in the installers alongside `uv` and `node`; SciQLop itself is
not bundled, it is installed from PyPI into the workspace venv on first launch.

## Why it is separate from the app

The launcher runs *before* SciQLop exists on the machine, so it cannot import
anything from it. That constraint is the point: one launcher binary must be able
to start every SciQLop version, old and new, which means its knowledge of the
app has to stay frozen and tiny.

Everything the launcher knows:

| Contract | Detail |
|---|---|
| Manifest keys it reads | `[workspace] name`, `sciqlop_version`, `python_version` |
| File it may create | `pyproject.toml`, **only when absent** — an existing one is the app's |
| How it starts the app | `.venv/bin/python -m SciQLop.sciqlop_app` |
| Environment it sets | `SCIQLOP_WORKSPACE_DIR`, `SCIQLOP_STARTUP_READY_FILE`, `SPEASY_SKIP_INIT_PROVIDERS=1`, `PYTHONNOUSERSITE=1` |
| Startup handshake | app touches the ready file → splash closes |
| Exit protocol | `64` restart same workspace, `65` switch to the name in `.sciqlop_switch_target` |

Plugin dependencies, appstore packages and workspace `requires` are deliberately
*not* here. The app owns the full `pyproject.toml`: it rewrites the file once
running and asks for a restart (`64`) when the contents changed.

## Layout

```
src/ui.hpp            the whole UI contract — six methods
src/ui_fltk.cpp       FLTK implementation (swap this file to change toolkit)
src/launcher.cpp      toolkit-independent: resolve, sync, supervise
src/process_*.cpp     subprocess + line-streamed output (POSIX / Win32)
src/manifest.cpp      the three manifest keys, and MRU workspace selection
src/project.cpp       bootstrap pyproject.toml
tests/                unit tests for the pure logic
```

## Build

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

FLTK and toml++ are fetched by CMake. On Linux the only system dependencies are
the X11/fontconfig headers (`libX11 libXext libXft libXinerama libXfixes
libXcursor libXrender fontconfig`); macOS and Windows need none.

## Release and consumption

Tagging `launcher-v*` builds four binaries and attaches them to the release
(`.github/workflows/launcher.yml`). The Linux one is built in
`manylinux_2_28` so it runs on distros older than the SciQLop build container.

The installer build scripts pin a version and digest in
`scripts/launcher.version` and fetch through `scripts/fetch_launcher.sh` (or
`.ps1`), exactly as they already do for `uv` and `node`.

To iterate without cutting a release:

```bash
SCIQLOP_LAUNCHER_BIN=$PWD/launcher/build/sciqlop-launcher sh scripts/appimage/build.sh
```

### Wiring into the installers

Not yet wired in: there is no launcher release to download, so adding the fetch
step would break all three builds today. When the distribution split lands, each
script gains one call next to its existing uv download:

```bash
# scripts/appimage/build.sh
sh "$SCRIPT_DIR/../fetch_launcher.sh" linux_x86_64 "$APPDIR/usr/bin/sciqlop-launcher"
cp SciQLop/resources/splash.png "$APPDIR/usr/bin/splash.png"
```

```bash
# scripts/macos/make_dmg.sh   ($ARCH is already computed for the uv download)
sh "$SCRIPT_DIR/../fetch_launcher.sh" "macos_$ARCH" "$MACOS_BIN/sciqlop-launcher"
```

```powershell
# scripts/windows/bundle.ps1  (replaces the cl.exe launcher.c compile)
& "$ScriptDir\..\fetch_launcher.ps1" -Destination "$PackageDir\SciQLop.exe"
```

The launcher looks for `uv` and `splash.png` beside its own binary, so it must
be installed in the same directory as the bundled uv.
