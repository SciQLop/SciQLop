#!/usr/bin/env bash
# Headless end-to-end test: real launcher, stub uv, stub application.
#
# Covers what the unit tests cannot — that the splash actually comes up, that
# subprocess output reaches it, that the ready-file handshake closes it, and
# that the restart/switch exit protocol loops correctly. A regression here (the
# window closing itself, output going nowhere) is invisible to ctest.
#
#   smoke_test.sh <path-to-sciqlop-launcher>
#
# No `set -e`: every check must run so one failure does not hide the others.
set -uo pipefail

LAUNCHER="${1:?usage: smoke_test.sh <launcher-binary>}"
LAUNCHER="$(cd "$(dirname "$LAUNCHER")" && pwd)/$(basename "$LAUNCHER")"

ROOT="$(mktemp -d)"
XVFB_PID=""
cleanup() {
    [ -n "$XVFB_PID" ] && kill "$XVFB_PID" 2>/dev/null
    rm -rf "$ROOT"
}
trap cleanup EXIT

export XDG_DATA_HOME="$ROOT/data"
WORKSPACES="$ROOT/data/sciqlop/workspaces"
LOG="$ROOT/data/sciqlop/last-launch.log"
mkdir -p "$ROOT/bin" "$WORKSPACES/default/.venv/bin" "$WORKSPACES/other/.venv/bin"
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

file_contains() { grep -q "$2" "$1" 2>/dev/null; }
equals() { [ "$1" = "$2" ]; }

Xvfb :91 -screen 0 1024x768x24 >/dev/null 2>&1 &
XVFB_PID=$!
export DISPLAY=:91
sleep 2

# --- case 1: successful launch, restart (64), then switch (65) --------------
cat > "$ROOT/bin/uv" <<'EOF'
#!/usr/bin/env bash
echo "Resolving dependencies" >&2
echo "Downloading sciqlop" >&2
exit 0
EOF
cat > "$WORKSPACES/default/.venv/bin/python" <<EOF
#!/usr/bin/env bash
: > "\$SCIQLOP_STARTUP_READY_FILE"
N=\$(cat "$ROOT/runs" 2>/dev/null || echo 0); N=\$((N + 1)); echo \$N > "$ROOT/runs"
echo "default run \$N"
[ "\$N" = "1" ] && exit 64
echo other > "\$SCIQLOP_WORKSPACE_DIR/.sciqlop_switch_target"
exit 65
EOF
cat > "$WORKSPACES/other/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
: > "$SCIQLOP_STARTUP_READY_FILE"
echo "other workspace started"
exit 0
EOF
chmod +x "$ROOT/bin/uv" "$WORKSPACES"/*/.venv/bin/python

echo "case 1: launch, restart, switch"
timeout 60 "$LAUNCHER" --workspace default
launcher_exit=$?
runs=$(cat "$ROOT/runs" 2>/dev/null || echo 0)

expect "launcher exits 0 after the switch chain" equals "$launcher_exit" 0
expect "default workspace ran twice (initial + restart)" equals "$runs" 2
expect "switch target was honoured" file_contains "$LOG" "other workspace started"
expect "uv output reached the session log" file_contains "$LOG" "uv"
expect "bootstrap pyproject.toml was generated" \
    file_contains "$WORKSPACES/default/pyproject.toml" "sciqlop"
expect "manifest was created for a new workspace" \
    file_contains "$WORKSPACES/default/workspace.sciqlop" 'name = "default"'

# --- case 2: a failing uv must not silently produce an empty venv ----------
echo "case 2: dependency resolution failure"
rm -rf "$WORKSPACES/failing"
mkdir -p "$WORKSPACES/failing/.venv/bin"
printf '#!/usr/bin/env bash\nexit 0\n' > "$WORKSPACES/failing/.venv/bin/python"
chmod +x "$WORKSPACES/failing/.venv/bin/python"
cat > "$ROOT/bin/uv" <<'EOF'
#!/usr/bin/env bash
echo "  x No solution found when resolving dependencies:" >&2
echo "  matplotlib==3.11.1 conflicts with matplotlib>=3.12" >&2
exit 1
EOF
chmod +x "$ROOT/bin/uv"

# The error window waits for the user, so the launcher is expected to be killed
# by the timeout here — what matters is that it stayed up rather than exiting
# silently, and that the cause was recorded.
timeout 8 "$LAUNCHER" --workspace failing
error_exit=$?

expect "launcher stayed up showing the error (killed by timeout)" equals "$error_exit" 124
expect "uv failure reason was written to the log" file_contains "$LOG" "No solution found"

echo
if [ "$failures" -eq 0 ]; then
    echo "smoke test passed"
else
    echo "smoke test failed ($failures checks)"
    echo "--- last-launch.log ---"
    cat "$LOG" 2>/dev/null
fi
exit "$failures"
