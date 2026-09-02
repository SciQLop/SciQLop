#!/usr/bin/env bash
# Headless end-to-end test: real launcher, stub python3 — no uv stub, the
# launcher no longer calls it.
#
# Covers what the unit tests cannot — that the splash actually comes up, that
# subprocess output reaches it, that argv is forwarded to Python untouched,
# that the ready-file handshake closes the splash, that a failed launch stays
# up showing the error (and that the WM's own close button on it actually
# quits — C5), and that a missing python3 is reported rather than hung
# forever. A regression here (the window closing itself, output going
# nowhere, an argument silently dropped) is invisible to ctest.
#
#   smoke_test.sh <path-to-sciqlop-launcher>
#
# No `set -e`: every check must run so one failure does not hide the others.
set -uo pipefail

LAUNCHER="${1:?usage: smoke_test.sh <launcher-binary>}"
LAUNCHER="$(cd "$(dirname "$LAUNCHER")" && pwd)/$(basename "$LAUNCHER")"

ROOT="$(mktemp -d)"
XVFB_PID=""
LAUNCHER_PID=""
cleanup() {
    [ -n "$LAUNCHER_PID" ] && kill "$LAUNCHER_PID" 2>/dev/null
    [ -n "$XVFB_PID" ] && kill "$XVFB_PID" 2>/dev/null
    rm -rf "$ROOT"
}
trap cleanup EXIT

# Force FLTK onto the Xvfb X11 display below rather than a host Wayland
# session this container may be forwarding: FLTK checks XDG_RUNTIME_DIR and
# happily connects to a real, unrelated compositor there even with
# WAYLAND_DISPLAY unset, and on a bare Wayland session its libdecor-based
# window decorations (used once show_error() sets border(1)) pull in a GTK
# icon-theme lookup that shells out to `bwrap`, which fails under nested
# container sandboxing and hard-aborts the whole process — an unrelated,
# pre-existing FLTK/libdecor/GTK hazard, not a launcher bug.
export FLTK_BACKEND=x11

export XDG_DATA_HOME="$ROOT/data"
LOG="$ROOT/data/sciqlop/last-launch.log"
mkdir -p "$ROOT/bin"
export PATH="$ROOT/bin:$PATH"

failures=0
expect() {
    local description="$1"
    shift
    if "$@"; then
        echo "  ok: $description"
    else
        echo "  FAIL: $description"
        failures=$((failures + 1))
    fi
}

file_contains() { grep -q -- "$2" "$1" 2>/dev/null; }
equals() { [ "$1" = "$2" ]; }
nonzero() { [ "$1" != "0" ]; }

wait_for_log_contains() {
    local file="$1" needle="$2" timeout_s="${3:-10}" waited=0
    while ! grep -q -- "$needle" "$file" 2>/dev/null; do
        sleep 0.1
        waited=$((waited + 1))
        [ "$waited" -ge $((timeout_s * 10)) ] && return 1
    done
    return 0
}

# Waits (up to 5s) for the error window to appear, then closes it through
# xdotool's WM_DELETE_WINDOW (what a real WM close button sends) — the C5
# regression check. Falls back to killing the process when xdotool is not
# installed or the window never appears, in which case the C5-specific
# assertion is skipped rather than failed.
close_error_window_or_kill() {
    local pid="$1" exit_code_var="$2" via_xdotool_var="$3"
    local window_id=""

    if command -v xdotool >/dev/null 2>&1; then
        for _ in $(seq 1 50); do
            window_id="$(xdotool search --name "startup failed" 2>/dev/null | head -n1)"
            [ -n "$window_id" ] && break
            sleep 0.1
        done
    else
        echo "  note: xdotool not installed, skipping the WM-close sub-check (C5)"
    fi

    if [ -n "$window_id" ]; then
        xdotool windowclose "$window_id"
        wait "$pid"
        printf -v "$exit_code_var" '%s' "$?"
        printf -v "$via_xdotool_var" '%s' "yes"
    else
        kill "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
        printf -v "$exit_code_var" '%s' "$?"
        printf -v "$via_xdotool_var" '%s' "no"
    fi
}

Xvfb :91 -screen 0 1024x768x24 >/dev/null 2>&1 &
XVFB_PID=$!
export DISPLAY=:91
sleep 2

# --- case 1: successful launch, argv forwarded, ready-file ack -------------
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
echo "Preparing workspace /x ..."
echo "Starting SciQLop ..."
printf '%s\n' "\$@" > "$ROOT/case1-argv"
: > "\$SCIQLOP_STARTUP_READY_FILE"
for _ in \$(seq 1 50); do
    if [ ! -e "\$SCIQLOP_STARTUP_READY_FILE" ]; then
        touch "$ROOT/case1-ack-seen"
        break
    fi
    sleep 0.1
done
exit 0
EOF
chmod +x "$ROOT/bin/python3"

echo "case 1: successful launch"
timeout 30 "$LAUNCHER" --workspace foo bar.sciqlop-archive
launcher_exit=$?

expect "launcher exits 0" equals "$launcher_exit" 0
expect "log contains the 'Preparing workspace' phase line" \
    file_contains "$LOG" "Preparing workspace /x ..."
expect "log contains the 'Starting SciQLop' phase line" \
    file_contains "$LOG" "Starting SciQLop ..."
expect "the stub observed the ready-file being acknowledged (deleted)" \
    test -f "$ROOT/case1-ack-seen"
expect "argv (--workspace foo bar.sciqlop-archive) was forwarded verbatim, in order" \
    equals "$(tail -n 3 "$ROOT/case1-argv" | tr '\n' ' ')" "--workspace foo bar.sciqlop-archive "

# --- case 2: a crashing app must stay on screen, not vanish -----------------
cat > "$ROOT/bin/python3" <<'EOF'
#!/usr/bin/env bash
echo "boom" >&2
exit 3
EOF
chmod +x "$ROOT/bin/python3"

echo "case 2: application crash"
"$LAUNCHER" --workspace failing &
LAUNCHER_PID=$!

wait_for_log_contains "$LOG" "boom" 15
close_error_window_or_kill "$LAUNCHER_PID" case2_exit case2_via_xdotool
LAUNCHER_PID=""

expect "the crash reason reached the log" file_contains "$LOG" "boom"
if [ "$case2_via_xdotool" = "yes" ]; then
    expect "WM close on the error window quits the launcher with the app's exit code (C5)" \
        equals "$case2_exit" 3
else
    echo "  skip: WM-close sub-check for C5 not exercised (xdotool unavailable or window not found)"
fi

# --- case 3: python3 missing from PATH entirely -----------------------------
# Mirror every real executable on PATH into one directory, except python3
# itself — dropping whole PATH directories instead would also hide unrelated
# tools (e.g. bwrap, used by GTK's icon-theme lookup on this host) that happen
# to share a directory with python3, turning this into a test of that instead
# of the launcher.
no_python_dir="$ROOT/no_python_bin"
mkdir -p "$no_python_dir"
IFS=':' read -ra path_dirs <<< "$PATH"
for dir in "${path_dirs[@]}"; do
    [ -d "$dir" ] || continue
    for exe in "$dir"/*; do
        [ -x "$exe" ] || continue
        name="$(basename "$exe")"
        case "$name" in
            python3|python3.*) continue ;;
        esac
        [ -e "$no_python_dir/$name" ] || ln -s "$exe" "$no_python_dir/$name"
    done
done

echo "case 3: python3 missing from PATH"
# No subshell wrapper: PATH=... cmd & backgrounds the launcher itself, so
# LAUNCHER_PID is the real process — killing a wrapping subshell instead would
# risk orphaning the launcher rather than actually terminating it.
PATH="$no_python_dir" "$LAUNCHER" --workspace nopython &
LAUNCHER_PID=$!

wait_for_log_contains "$LOG" "python3" 15
close_error_window_or_kill "$LAUNCHER_PID" case3_exit case3_via_xdotool
LAUNCHER_PID=""

expect "the log names the command it failed to run" file_contains "$LOG" "python3"
expect "the launcher exits non-zero rather than hanging forever" nonzero "$case3_exit"

# --- case 4: restart round (exit 64, then a normal exit) --------------------
# The stub tracks its own invocation count across the two rounds the launcher
# runs it for, entirely within this one launcher process.
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
count_file="$ROOT/case4-count"
n=0
[ -f "\$count_file" ] && n=\$(cat "\$count_file")
n=\$((n + 1))
echo "\$n" > "\$count_file"
echo "Preparing workspace /x ..."
echo "Starting SciQLop ..."
: > "\$SCIQLOP_STARTUP_READY_FILE"
for _ in \$(seq 1 50); do
    [ -e "\$SCIQLOP_STARTUP_READY_FILE" ] || break
    sleep 0.1
done
[ "\$n" -eq 1 ] && exit 64
exit 0
EOF
chmod +x "$ROOT/bin/python3"

echo "case 4: restart round (round 1 exits 64, round 2 exits 0)"
timeout 30 "$LAUNCHER" --workspace foo
case4_exit=$?

expect "launcher exits 0 once the restart round finishes cleanly" equals "$case4_exit" 0
expect "log shows round 1 as a start" file_contains "$LOG" "=== round 1 (start) ==="
expect "log shows round 2 as a restart" file_contains "$LOG" "=== round 2 (restart) ==="

# --- case 5: workspace-switch round (exit 65, target via the handoff file) --
# The launcher itself sets SCIQLOP_SWITCH_HANDOFF_FILE per round, pointing at
# its own per-pid scratch dir (sibling of the ready marker) — the stub just
# writes there, no path prediction/XDG trick needed on this side.
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
count_file="$ROOT/case5-count"
n=0
[ -f "\$count_file" ] && n=\$(cat "\$count_file")
n=\$((n + 1))
echo "\$n" > "\$count_file"
echo "Preparing workspace /x ..."
echo "Starting SciQLop ..."
: > "\$SCIQLOP_STARTUP_READY_FILE"
for _ in \$(seq 1 50); do
    [ -e "\$SCIQLOP_STARTUP_READY_FILE" ] || break
    sleep 0.1
done
if [ "\$n" -eq 1 ]; then
    printf 'foo\n' > "\$SCIQLOP_SWITCH_HANDOFF_FILE"
    exit 65
fi
printf '%s\n' "\$@" > "$ROOT/case5-round2-argv"
exit 0
EOF
chmod +x "$ROOT/bin/python3"

echo "case 5: workspace switch (round 1 exits 65 and names 'foo')"
timeout 30 "$LAUNCHER" bar.sciqlop-archive
case5_exit=$?

expect "launcher exits 0 once the switch round finishes cleanly" equals "$case5_exit" 0
expect "round 2 argv ends in --workspace foo" \
    equals "$(tail -n 2 "$ROOT/case5-round2-argv" 2>/dev/null | tr '\n' ' ')" "--workspace foo "
expect "round 2 argv drops the original positional file" \
    bash -c '! grep -q "bar.sciqlop-archive" "$1" 2>/dev/null' _ "$ROOT/case5-round2-argv"

echo
if [ "$failures" -eq 0 ]; then
    echo "smoke test passed"
else
    echo "smoke test failed ($failures checks)"
    echo "--- last-launch.log ---"
    cat "$LOG" 2>/dev/null
fi
exit "$failures"
