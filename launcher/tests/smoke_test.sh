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
LOG_DIR="$ROOT/data/sciqlop/logs"
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

# Every launcher process writes its own dated log; each case starts from an
# empty logs/ directory so a check only ever sees its own case's output.
start_case() {
    rm -rf "$LOG_DIR"
    echo "$1"
}
log_contains() { cat "$LOG_DIR"/sciqlop-*.log 2>/dev/null | grep -q -- "$1"; }
log_count() { find "$LOG_DIR" -name 'sciqlop-*.log' 2>/dev/null | wc -l | tr -d ' '; }

wait_for_log_contains() {
    local needle="$1" timeout_s="${2:-10}" waited=0
    while ! log_contains "$needle"; do
        sleep 0.1
        waited=$((waited + 1))
        [ "$waited" -ge $((timeout_s * 10)) ] && return 1
    done
    return 0
}

# `wait` for *pid*, but kill it after *timeout_s* seconds: a click that
# misses must fail the test, never hang it (and CI with it).
wait_bounded() {
    local pid="$1" timeout_s="$2"
    ( sleep "$timeout_s"; kill "$pid" 2>/dev/null ) &
    local watchdog=$!
    wait "$pid"
    local code=$?
    kill "$watchdog" 2>/dev/null
    wait "$watchdog" 2>/dev/null
    return "$code"
}

# The title changes before the window grows to the error layout, so wait for
# the layout's height (458, see ui_fltk.cpp show_error) before clicking.
find_error_window() {
    local window_id=""
    for _ in $(seq 1 100); do
        window_id="$(xdotool search --name "startup failed" 2>/dev/null | head -n1)"
        if [ -n "$window_id" ] &&
            xdotool getwindowgeometry "$window_id" 2>/dev/null | grep -q "x458"; then
            echo "$window_id"
            return
        fi
        sleep 0.1
    done
}

# `windowclose` only exists in xdotool >= 3.2021; EPEL 8 ships the 2016 one.
xdotool_can_close() { xdotool help 2>&1 | grep -qw windowclose; }

# Waits for the error window to appear, then closes it through xdotool's
# WM_DELETE_WINDOW (what a real WM close button sends) — the C5 regression
# check. Falls back to killing the process when xdotool is not installed, is
# too old to send WM_DELETE_WINDOW, or the window never appears, in which
# case the C5-specific assertion is skipped rather than failed.
close_error_window_or_kill() {
    local pid="$1" exit_code_var="$2" via_xdotool_var="$3"
    local window_id=""

    if command -v xdotool >/dev/null 2>&1 && xdotool_can_close; then
        window_id="$(find_error_window)"
    else
        echo "  note: xdotool missing or without windowclose, skipping the WM-close sub-check (C5)"
    fi

    if [ -n "$window_id" ]; then
        xdotool windowclose "$window_id"
        wait_bounded "$pid" 20
        printf -v "$exit_code_var" '%s' "$?"
        printf -v "$via_xdotool_var" '%s' "yes"
    else
        kill "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
        printf -v "$exit_code_var" '%s' "$?"
        printf -v "$via_xdotool_var" '%s' "no"
    fi
}

# -displayfd lets Xvfb pick a free display: a fixed one silently lands every
# window on whatever other X server already holds it.
Xvfb -displayfd 3 -screen 0 1024x768x24 3>"$ROOT/display" >/dev/null 2>&1 &
XVFB_PID=$!
for _ in $(seq 1 50); do
    [ -s "$ROOT/display" ] && break
    sleep 0.1
done
export DISPLAY=":$(tr -d '[:space:]' < "$ROOT/display")"

# --- case 1: successful launch, argv forwarded, ready-file ack -------------
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
echo "Preparing workspace /x ..."
echo "Starting SciQLop ..."
printf '%s\n' "\$@" > "$ROOT/case1-argv"
printf '%s' "\$SCIQLOP_SESSION_LOG" > "$ROOT/case1-session-log"
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

start_case "case 1: successful launch"
timeout 30 "$LAUNCHER" --workspace foo bar.sciqlop-archive
launcher_exit=$?

expect "launcher exits 0" equals "$launcher_exit" 0
expect "log contains the 'Preparing workspace' phase line" \
    log_contains "Preparing workspace /x ..."
expect "log contains the 'Starting SciQLop' phase line" \
    log_contains "Starting SciQLop ..."
expect "the stub observed the ready-file being acknowledged (deleted)" \
    test -f "$ROOT/case1-ack-seen"
expect "argv (--workspace foo bar.sciqlop-archive) was forwarded verbatim, in order" \
    equals "$(tail -n 3 "$ROOT/case1-argv" | tr '\n' ' ')" "--workspace foo bar.sciqlop-archive "
expect "exactly one dated session log was written" equals "$(log_count)" 1
expect "SCIQLOP_SESSION_LOG names that log, so Python does not write a second one" \
    test -f "$(cat "$ROOT/case1-session-log" 2>/dev/null)"
expect "the log starts with the launcher header" \
    log_contains "SciQLop launcher"
expect "each tee'd line starts with its local time, to the millisecond" \
    log_contains "^[0-9]\{4\}-[0-9][0-9]-[0-9][0-9] [0-9:]\{8\}\.[0-9]\{3\} \[out\] Starting SciQLop \.\.\.$"

# --- case 1b: rotation keeps the ten newest logs, this launch's included ----
start_case "case 1b: log rotation"
mkdir -p "$LOG_DIR"
for day in 10 11 12 13 14 15 16 17 18 19 20 21; do
    : > "$LOG_DIR/sciqlop-202001${day}-000000-1.log"
done
timeout 30 "$LAUNCHER" --workspace foo
expect "rotation leaves 10 logs" equals "$(log_count)" 10
expect "the oldest logs are gone" test ! -e "$LOG_DIR/sciqlop-20200112-000000-1.log"
expect "this launch's log survived" log_contains "Starting SciQLop ..."

# --- case 2: a crashing app must stay on screen, not vanish -----------------
cat > "$ROOT/bin/python3" <<'EOF'
#!/usr/bin/env bash
echo "boom" >&2
exit 3
EOF
chmod +x "$ROOT/bin/python3"

start_case "case 2: application crash"
"$LAUNCHER" --workspace failing &
LAUNCHER_PID=$!

wait_for_log_contains "boom" 15
close_error_window_or_kill "$LAUNCHER_PID" case2_exit case2_via_xdotool
LAUNCHER_PID=""

expect "the crash reason reached the log" log_contains "boom"
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

start_case "case 3: python3 missing from PATH"
# No subshell wrapper: PATH=... cmd & backgrounds the launcher itself, so
# LAUNCHER_PID is the real process — killing a wrapping subshell instead would
# risk orphaning the launcher rather than actually terminating it.
PATH="$no_python_dir" "$LAUNCHER" --workspace nopython &
LAUNCHER_PID=$!

wait_for_log_contains "python3" 15
close_error_window_or_kill "$LAUNCHER_PID" case3_exit case3_via_xdotool
LAUNCHER_PID=""

expect "the log names the command it failed to run" log_contains "python3"
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

start_case "case 4: restart round (round 1 exits 64, round 2 exits 0)"
timeout 30 "$LAUNCHER" --workspace foo
case4_exit=$?

expect "launcher exits 0 once the restart round finishes cleanly" equals "$case4_exit" 0
expect "log shows round 1 as a start" log_contains "=== round 1 (start) ==="
expect "log shows round 2 as a restart" log_contains "=== round 2 (restart) ==="

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

start_case "case 5: workspace switch (round 1 exits 65 and names 'foo')"
timeout 30 "$LAUNCHER" bar.sciqlop-archive
case5_exit=$?

expect "launcher exits 0 once the switch round finishes cleanly" equals "$case5_exit" 0
expect "round 2 argv ends in --workspace foo" \
    equals "$(tail -n 2 "$ROOT/case5-round2-argv" 2>/dev/null | tr '\n' ' ')" "--workspace foo "
expect "round 2 argv drops the original positional file" \
    bash -c '! grep -q "bar.sciqlop-archive" "$1" 2>/dev/null' _ "$ROOT/case5-round2-argv"

# --- case 6: restart-budget exhausted (R3) -----------------------------
# A stub that always asks to restart (exit 64) never stops on its own — the
# launcher must give up rather than loop forever. 1 initial round + 3
# tolerated restarts = 4 invocations before the 5th is refused outright
# (no 5th subprocess launch at all) and the "keeps restarting" error shows.
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
count_file="$ROOT/case6-count"
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
exit 64
EOF
chmod +x "$ROOT/bin/python3"

start_case "case 6: restart-budget exhausted (app keeps asking to restart)"
"$LAUNCHER" --workspace loop &
LAUNCHER_PID=$!

waited=0
while [ "$(cat "$ROOT/case6-count" 2>/dev/null)" != "4" ]; do
    sleep 0.1
    waited=$((waited + 1))
    [ "$waited" -ge 150 ] && break
done

close_error_window_or_kill "$LAUNCHER_PID" case6_exit case6_via_xdotool
LAUNCHER_PID=""

expect "the app was invoked exactly 4 times (1 start + 3 tolerated restarts, no 5th)" \
    equals "$(cat "$ROOT/case6-count" 2>/dev/null)" "4"
if [ "$case6_via_xdotool" = "yes" ]; then
    expect "the restart-budget-exhausted error is shown and quitting exits 1 (R3)" \
        equals "$case6_exit" 1
else
    echo "  skip: restart-budget error window sub-check not exercised (xdotool unavailable or window not found)"
fi

# --- case 7: "Restart SciQLop" on the error view starts a new round ---------
cat > "$ROOT/bin/python3" <<EOF
#!/usr/bin/env bash
count=\$(( \$(cat "$ROOT/case7-count" 2>/dev/null || echo 0) + 1 ))
echo "\$count" > "$ROOT/case7-count"
if [ "\$count" -eq 1 ]; then
    echo "first run crashes" >&2
    exit 139
fi
: > "\$SCIQLOP_STARTUP_READY_FILE"
exit 0
EOF
chmod +x "$ROOT/bin/python3"

start_case "case 7: Restart SciQLop after a crash"
if command -v xdotool >/dev/null 2>&1; then
    "$LAUNCHER" --workspace crashy &
    LAUNCHER_PID=$!
    window_id="$(find_error_window)"
    if [ -n "$window_id" ]; then
        # Centre of the Restart button: x = WIDTH - PAD - 75, y = 406 + 16.
        # The window can reach its final size a moment before the button
        # takes clicks, so retry until the second round has started.
        for _ in $(seq 1 20); do
            xdotool mousemove --window "$window_id" 625 422 click 1 2>/dev/null
            sleep 0.5
            [ "$(cat "$ROOT/case7-count" 2>/dev/null)" = 2 ] && break
        done
        wait_bounded "$LAUNCHER_PID" 20
        case7_exit=$?
        LAUNCHER_PID=""
        expect "Restart ran the app a second time" equals "$(cat "$ROOT/case7-count" 2>/dev/null)" 2
        expect "the restarted round exits cleanly" equals "$case7_exit" 0
        expect "both rounds share one session log" equals "$(log_count)" 1
        expect "the log shows the restart round" log_contains "=== round 2 (restart) ==="
    else
        kill "$LAUNCHER_PID" 2>/dev/null
        wait "$LAUNCHER_PID" 2>/dev/null
        LAUNCHER_PID=""
        expect "the error window with the Restart button appeared" false
    fi
else
    echo "  skip: xdotool not installed, the Restart button cannot be clicked"
fi

echo
if [ "$failures" -eq 0 ]; then
    echo "smoke test passed"
else
    echo "smoke test failed ($failures checks)"
    echo "--- session log ---"
    cat "$LOG_DIR"/sciqlop-*.log 2>/dev/null
fi
exit "$failures"
