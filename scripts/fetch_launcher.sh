#!/usr/bin/env bash
# Fetch the pinned launcher binary and verify its digest.
#
#   fetch_launcher.sh <platform> <destination>
#     platform: linux_x86_64 | macos_arm64 | macos_x86_64
#
# Set SCIQLOP_LAUNCHER_BIN to a locally built binary to bypass the download —
# without it, iterating on the launcher would need a release for every change.
set -euo pipefail

PLATFORM="$1"
DEST="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=launcher.version
source "$SCRIPT_DIR/launcher.version"

mkdir -p "$(dirname "$DEST")"

if [ -n "${SCIQLOP_LAUNCHER_BIN:-}" ]; then
    echo "Using local launcher: $SCIQLOP_LAUNCHER_BIN"
    cp "$SCIQLOP_LAUNCHER_BIN" "$DEST"
    chmod +x "$DEST"
    exit 0
fi

case "$PLATFORM" in
    linux_x86_64)  ASSET="sciqlop-launcher-linux-x86_64" ;;
    macos_arm64)   ASSET="sciqlop-launcher-macos-arm64" ;;
    macos_x86_64)  ASSET="sciqlop-launcher-macos-x86_64" ;;
    *) echo "Unknown launcher platform: $PLATFORM" >&2; exit 1 ;;
esac

EXPECTED_VAR="LAUNCHER_SHA256_${PLATFORM}"
EXPECTED="${!EXPECTED_VAR:-}"
if [ -z "$EXPECTED" ]; then
    echo "No pinned digest for $PLATFORM in launcher.version" >&2
    exit 1
fi

# All-zero digest is the placeholder launcher.version ships until a real
# launcher-v$LAUNCHER_VERSION release exists. Exit 3 (a distinct code from
# every other failure here) rather than 404ing CI — callers (build.sh) tell
# this apart from "not released yet is fine" vs. "not released yet is fatal"
# by whether a release build is running.
case "$EXPECTED" in
    *[!0]*) ;;
    *)
        rm -f "$DEST"
        echo "launcher $LAUNCHER_VERSION not pinned for $PLATFORM (placeholder digest) — skipping"
        exit 3
        ;;
esac

URL="https://github.com/$LAUNCHER_REPO/releases/download/launcher-v$LAUNCHER_VERSION/$ASSET"
echo "Downloading launcher $LAUNCHER_VERSION ($PLATFORM)..."
if ! curl -fsSL -o "$DEST" "$URL"; then
    rm -f "$DEST"
    echo "Failed to download launcher $LAUNCHER_VERSION ($PLATFORM)" >&2
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL="$(sha256sum "$DEST" | cut -d' ' -f1)"
else
    ACTUAL="$(shasum -a 256 "$DEST" | cut -d' ' -f1)"
fi

if [ "$ACTUAL" != "$EXPECTED" ]; then
    rm -f "$DEST"
    echo "Launcher digest mismatch for $PLATFORM" >&2
    echo "  expected $EXPECTED" >&2
    echo "  actual   $ACTUAL" >&2
    exit 1
fi

chmod +x "$DEST"
echo "Launcher verified: $DEST"
