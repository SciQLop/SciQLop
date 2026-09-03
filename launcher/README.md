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
| How it starts one round | `python3 -I -m SciQLop.app` + passthrough args + `--workspace <ws>` (if set) + the positional file (if set) |
| Environment it sets | `SCIQLOP_STARTUP_READY_FILE`, `SCIQLOP_SWITCH_HANDOFF_FILE` |
| Startup handshake | app touches the ready file → splash closes |
| Restart (exit `64`) | runs another round with the same options |
| Workspace switch (exit `65`) | reads the target from the handoff file, runs another round with `--workspace <target>` and no positional file |
| Final exit code | whatever the last round's session exits with |

Workspace *resolution* (`--workspace`/`-w`, a `.sciqlop`/`.sciqlop-archive`
file, the reopen-last-workspace setting) and venv/dependency preparation are
entirely Python's (`SciQLop/sciqlop_launcher.py`) — duplicating that here
would just be a second copy of already-tested logic to keep in sync. The
launcher owns *when* to run another round: it drives the restart/switch loop
itself and Python runs exactly one session per round under it (see "Round
loop" below).

## Finding the interpreter

On Linux/macOS, AppRun / the macOS wrapper script already put a bundled
interpreter on `PATH` before running this launcher, so it just execs
`python3`. Windows has no such wrapper — the launcher itself is the package's
entry point (`SciQLop.exe`, next to `python\`, `node\`, `uv\`) — so it first
looks for one next to its own binary: `<exe_dir>/python/python.exe` on
Windows, `<exe_dir>/python/bin/python3` elsewhere
(`paths::bundled_python()`). When found, it runs that absolute path instead
of the ambient `python3`/`python.exe`, and prepends `<exe_dir>/node`,
`<exe_dir>/uv` and the interpreter's own Scripts/bin directory to the child's
`PATH` (`paths::bundled_path_prefix()`) alongside `SCIQLOP_BUNDLED=1` — the
same environment `scripts/windows/launcher.c` used to set up by hand. When no
bundled interpreter is found (a dev checkout, or a bundle whose own wrapper
already resolves python some other way), this is a no-op and behavior is
unchanged.

## Layout

```
src/ui.hpp            the whole UI contract — six methods
src/ui_fltk.cpp        FLTK implementation (swap this file to change toolkit)
src/launcher.cpp       toolkit-independent: argv splitting, one round's supervision, phase-line classifying, the handoff file
src/main.cpp           the round loop: a fresh Ui per round, decides the next round's options from the exit code
src/process_*.cpp      subprocess + line-streamed output (POSIX / Win32)
src/paths.cpp          platform data/executable locations, bundled-interpreter discovery
src/win/               Windows-only resource: DPI-awareness/supportedOS manifest (WIN32 builds only)
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
`.ps1`), exactly as they already do for `uv` and `node`. `fetch_launcher.sh`
exits `3` (rather than downloading) while `launcher.version` still carries the
all-zero placeholder digest — `scripts/appimage/build.sh` treats that as fatal
when `$RELEASE` is set (a real release must not silently ship without the
launcher) and as a warn-and-continue-without-it otherwise.

To iterate without cutting a release:

```bash
SCIQLOP_LAUNCHER_BIN=$PWD/launcher/build/sciqlop-launcher sh scripts/appimage/build.sh
```

### Wiring into the installers

Wired into all three platforms — each fetches through
`fetch_launcher.sh`/`.ps1` and places the binary where that platform's app
already looks for its entry point:

| Platform | Lands at | Splash source |
|---|---|---|
| Linux (AppImage) | `$APPDIR/opt/launcher/sciqlop-launcher`, `AppRun` execs it | copied next to it |
| macOS (`make_dmg.sh`) | `SciQLop.app/Contents/MacOS/sciqlop-launcher`; the generated `Contents/MacOS/SciQLop` wrapper execs it, forwarding `"$@"` | copied next to it |
| Windows (`bundle.ps1`, `make_online_installer.ps1`) | `SciQLop.exe` at the package root — it *is* the entry point (see installer.iss/make_msix.ps1) | copied next to it |

The launcher looks for `splash.png` beside its own binary, so it must be
installed in the same directory as the launcher itself, on every platform.

On Linux/macOS `AppRun`/the wrapper script fall back to a direct
`python3 -I -m SciQLop.app` when no launcher binary was fetched (e.g. a build
made before `launcher-v0.1.0` existed, or a dev iteration with
`$RELEASE` unset — see `fetch_launcher.sh`'s exit-3 handling). Windows has no
such fallback — `SciQLop.exe` *is* the package's entry point — so
`bundle.ps1`/`make_online_installer.ps1` treat a missing launcher as fatal
unconditionally, rather than warn-and-continue.

## Startup-ready handshake

The ready marker and the workspace-switch handoff file both live in the same
per-process temp directory (`$TMPDIR/sciqlop-launcher-<pid>/ready` and
`.../next-workspace`), never inside a workspace and never at a fixed
`user_data_dir()` path — the launcher no longer resolves or even knows the
workspace directory, and a fixed path would either go stale (a launcher
killed after Python wrote the handoff file but before this round read it) or
be shared between two concurrent launcher instances. The directory is created
fresh per round and removed entirely once that round ends.

## Round loop

`main.cpp` runs a `for (;;)` loop, one fresh `Ui` per round, and decides the
next round's `Options` purely from the exit code `run_session()` returns:

- `0` (or anything else): the loop ends, that code is the launcher's own exit
  code.
- `64` (restart): another round with the same `Options` — same workspace,
  positional file and passthrough args as the round that asked for it. Capped
  at `RESTART_BUDGET` (3) restart rounds inside `RESTART_WINDOW` (60s) —
  beyond that a restart loop looks identical to a crash loop, so `main.cpp`
  gives up with an error instead of spinning forever. Workspace switches
  don't count toward the cap.
- `65` (switch workspace): `run_app()` reads, trims and deletes the round's
  handoff file (`take_switch_target()`, on the per-pid path it put in
  `SCIQLOP_SWITCH_HANDOFF_FILE` for that round — see above) *before*
  returning, while the scratch directory holding it is still alive, and
  hands the target up via `SessionResult`. If a target was found, the next
  round runs with `--workspace <target>` and no positional file; if the
  handoff file was missing or blank, the loop ends — after posting an error
  to the still-live splash, since by the time `run_session()` returns its
  window has already closed and can no longer show anything.

Python's side of the handoff: `SCIQLOP_STARTUP_READY_FILE` being set in its
environment (`READY_FILE_ENV`) tells `sciqlop_launcher.py`'s `main()` a native
launcher owns the round loop, so it must run exactly one session instead of
its own internal restart/switch loop. On a `65` with a target, it writes that
target (plain text) to the path in `SCIQLOP_SWITCH_HANDOFF_FILE`
(`SWITCH_HANDOFF_FILE_ENV`) — the launcher always sets this alongside
`SCIQLOP_STARTUP_READY_FILE`, and `_switch_handoff_path()` raises rather than
falling back to some other path if it's ever missing in native mode.

The session log (`last-launch.log`) is truncated once per launcher process —
on round 1 only — and gets a `=== round N (start|restart|switch) ===` marker
at the start of every round after that; a failing round's output must survive
into the next round's log, since the error window points at this file.
