# SciQLop launcher

A small, statically-linked C++ binary that shows a native splash while
SciQLop starts. It ships in the installers alongside `uv` and `node`; SciQLop
itself is not bundled, it is installed from PyPI into the workspace venv on
first launch.

## Why it is separate from the app

The launcher runs *before* SciQLop exists on the machine, so it cannot import
anything from it. That constraint is the point: one launcher binary must be
able to start every SciQLop version, old and new, which means its knowledge of
the app has to stay frozen and tiny.

Everything the launcher knows:

| Contract | Detail |
|---|---|
| How it starts the app | forwards its own argv untouched to `python3 -I -m SciQLop.app <argv>` |
| Environment it sets | `SCIQLOP_STARTUP_READY_FILE` |
| Startup handshake | app touches the ready file → splash closes |
| Exit code | whatever Python's own `main()` finally returns |

Workspace resolution (`--workspace`/`-w`, a `.sciqlop`/`.sciqlop-archive`
file, the reopen-last-workspace setting), venv/dependency preparation, and the
restart (`64`)/switch-workspace (`65`) loop are entirely Python's
(`SciQLop/sciqlop_launcher.py`). Duplicating that here would just be a second
copy of already-tested logic to keep in sync — the launcher's only job is
forwarding argv and showing a splash while that code runs.

## Layout

```
src/ui.hpp            the whole UI contract — six methods
src/ui_fltk.cpp        FLTK implementation (swap this file to change toolkit)
src/launcher.cpp       toolkit-independent: forward argv, supervise, classify phase lines
src/process_*.cpp      subprocess + line-streamed output (POSIX / Win32)
tests/                 unit tests for the pure logic, plus the end-to-end smoke test
```

## Build

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
tests/smoke_test.sh build/sciqlop-launcher
```

FLTK is fetched by CMake. On Linux the only system dependencies are the
X11/fontconfig headers (`libX11 libXext libXft libXinerama libXfixes
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

The launcher looks for `splash.png` beside its own binary, so it must be
installed in the same directory as the bundled uv.

## Startup-ready handshake

The ready-file marker lives in its own per-process temp directory
(`$TMPDIR/sciqlop-launcher-<pid>/ready`), never inside a workspace — the
launcher no longer resolves or even knows the workspace directory, and two
concurrent launcher instances would otherwise fight over the same file. The
directory is created fresh per session and removed entirely once the session
ends.
