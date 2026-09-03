#! /usr/bin/env bash
set -eo pipefail
HERE=$(dirname $BASH_SOURCE)
SCIQLOP_ROOT=$HERE/../../
DIST=$SCIQLOP_ROOT/dist
ICONDIR=$DIST/SciQLop.app/Contents/Resources/SciQLop.iconset
ARCH=$(uname -m)

PYTHON_VERSION=3.14
NODE_VERSION=24.17.0
UV_VERSION=0.11.21

mkdir -p $DIST

mkdir -p $DIST/SciQLop.app/Contents/MacOS
mkdir -p $DIST/SciQLop.app/Contents/Resources/usr/local
mkdir -p $ICONDIR

export MACOSX_DEPLOYMENT_TARGET=11.0
export PREFIX_ABS=$(realpath $DIST/SciQLop.app/Contents/Resources/usr/local)
export SAVED_PATH=$PATH
export PATH=$PREFIX_ABS/bin:$PATH

for SIZE in 16 32 64 128 256 512; do
sips -z $SIZE $SIZE $SCIQLOP_ROOT/SciQLop/resources/icons/SciQLop.png --out $ICONDIR/icon_${SIZE}x${SIZE}.png ;
done

for SIZE in 32 64 256 512; do
sips -z $SIZE $SIZE $SCIQLOP_ROOT/SciQLop/resources/icons/SciQLop.png --out $ICONDIR/icon_$(expr $SIZE / 2)x$(expr $SIZE / 2)x2.png ;
done

iconutil -c icns -o $DIST/SciQLop.app/Contents/Resources/SciQLop.icns $ICONDIR
rm -rf $ICONDIR

python3 $HERE/make_info_dot_plist.py > $DIST/SciQLop.app/Contents/Info.plist

cat <<'EOT' > $DIST/SciQLop.app/Contents/MacOS/SciQLop
#! /usr/bin/env bash
# Quote every expansion below: Finder renames a second copy of the app to
# something like "SciQLop 2.app", and an unquoted $BASH_SOURCE/$HERE/
# $RESOURCES word-splits on that space, sending `dirname` two arguments and
# turning the final python3 invocation into "/path/to/SciQLop" "2.app/..." —
# bash then tries to execute the directory, failing with "is a directory".
export HERE=$(dirname "$BASH_SOURCE")
export RESOURCES="$HERE/../Resources"
export PATH="$RESOURCES/opt/uv:$RESOURCES/usr/local/bin/:/usr/bin:/bin:/usr/sbin:/sbin"
export LD_LIBRARY_PATH="$RESOURCES/usr/local/lib"
export DYLD_LIBRARY_PATH="$RESOURCES/usr/local/lib:$RESOURCES/usr/local/bin/"
export QTWEBENGINE_CHROMIUM_FLAGS="--single-process"
SSL_CERT_FILE=$("$RESOURCES/usr/local/bin/python3" -m certifi 2>/dev/null || true)
if [ -n "$SSL_CERT_FILE" ]; then
    export SSL_CERT_FILE
    export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
fi
export SCIQLOP_BUNDLED="1"
if [ -x "$HERE/sciqlop-launcher" ]; then
    exec "$HERE/sciqlop-launcher" "$@"
fi
exec "$RESOURCES/usr/local/bin/python3" -m SciQLop.app "$@"
EOT

chmod +x $DIST/SciQLop.app/Contents/MacOS/SciQLop


function download_and_extract() {
  EXTENSION="${1##*.}"
  DESTFILE=$DIST/$(basename $1)
  FOLDER_NAME=$(basename $1 .$EXTENSION)
  rm -rf $DIST/$FOLDER_NAME
  if [[ -f $DESTFILE ]]; then
    echo "File $DESTFILE already exists"
  else
    echo "Downloading $1"
    curl -fLsS $1 -o $DESTFILE
  fi
  if [[ $EXTENSION == "zip" ]]; then
    unzip $DESTFILE -d $DIST &> /dev/null
  else
    tar xvz -C $DIST -f $DESTFILE &> /dev/null
  fi
}

########################################
# Fetch uv standalone
########################################

mkdir -p $DIST/SciQLop.app/Contents/Resources/opt/uv

if [[ $ARCH == "arm64" ]]; then
  UV_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-apple-darwin.tar.gz"
else
  UV_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-apple-darwin.tar.gz"
fi

if [[ ! -f $DIST/uv.tar.gz ]]; then
  curl -fLsS -o $DIST/uv.tar.gz "$UV_URL"
fi

tar -xzf $DIST/uv.tar.gz -C $DIST
cp $DIST/uv-*/uv $DIST/SciQLop.app/Contents/Resources/opt/uv/
chmod +x $DIST/SciQLop.app/Contents/Resources/opt/uv/uv

UV_BIN=$DIST/SciQLop.app/Contents/Resources/opt/uv/uv

########################################
# Fetch Python (python-build-standalone via uv)
#
# python-build-standalone is fully self-contained and relocatable: its install
# names are @executable_path/@loader_path-relative, it bundles its own OpenSSL,
# and it has no Homebrew linkage — so this replaces both the from-source OpenSSL
# and CPython builds and drops the old libintl/gettext hack entirely. We stage
# it under a temp install-dir, then merge its prefix into usr/local/ so python3
# lands at usr/local/bin/python3 — the path the launcher and the signing pass
# already expect. bin/ and lib/ stay siblings, so the @executable_path/../lib
# install names keep resolving.
########################################

PY_STAGING=$DIST/python-staging
rm -rf $PY_STAGING
$UV_BIN python install $PYTHON_VERSION --install-dir $PY_STAGING
# uv also drops an unversioned alias symlink (cpython-3.14-...) next to the
# real patch-versioned directory (cpython-3.14.6-...); `-type d` excludes it
# since find doesn't follow symlinks for -type, so this always resolves to
# the real install even if the alias is absent or dangling (seen on GH
# Actions macOS runners).
PBS_DIR=$(find $PY_STAGING -mindepth 1 -maxdepth 1 -type d -name 'cpython-*' | head -1)
rsync -aq $PBS_DIR/ $PREFIX_ABS/

PYTHON_BIN=$PREFIX_ABS/bin/python3

# Ensure the python3 entry point exists (some builds only ship python3.x).
ln -sf python$PYTHON_VERSION $PREFIX_ABS/bin/python3

# Remove the PEP 668 marker so `uv pip install` works against this interpreter.
find $PREFIX_ABS/lib -maxdepth 2 -name EXTERNALLY-MANAGED -delete

########################################
# Install SciQLop using uv
########################################

echo "Installing SciQLop launcher into bundle..."
# The bare package is only the launcher — read the manifest/settings, then
# drive uv. It never imports the GUI stack (test_launcher_thin_imports.py),
# so it doesn't need [all] here: the application (and plugin
# python_dependencies, and — for a .dev version — speasy/SciQLop straight
# from git main) is installed into each workspace's own venv at first
# launch by prepare_workspace(). Installing any of that into this bundled
# Python would bake the whole app into the bundle, defeating the point of
# the self-contained-workspace split.
$UV_BIN pip install -q --reinstall --no-cache --python $PYTHON_BIN "$SCIQLOP_ROOT"

########################################
# SSL certificates (for systems without a usable system CA bundle)
########################################

$UV_BIN pip install --python $PYTHON_BIN certifi

########################################
# Bundle native launcher (splash while the bundled Python above prepares the
# workspace and starts the app — see launcher/src/launcher.cpp)
########################################

# shellcheck source=../launcher.version
. "$SCIQLOP_ROOT/scripts/launcher.version"

MACOS_BIN=$DIST/SciQLop.app/Contents/MacOS
# uname -m already returns "arm64"/"x86_64", matching fetch_launcher.sh's
# macos_arm64/macos_x86_64 platform names verbatim.
set +e
"$SCIQLOP_ROOT/scripts/fetch_launcher.sh" "macos_$ARCH" "$MACOS_BIN/sciqlop-launcher"
FETCH_LAUNCHER_STATUS=$?
set -e

# Exit 3 means launcher.version still carries the placeholder digest (no
# launcher-v<ver> release exists yet) — fetch_launcher.sh already removed any
# partial file. Fatal on a real release build ($RELEASE set, same convention
# as scripts/appimage/build.sh), a warning otherwise. Any other non-zero exit
# (bad download, digest mismatch, ...) is fatal either way.
if [[ "$FETCH_LAUNCHER_STATUS" -eq 3 ]]; then
  if [[ -n "$RELEASE" ]]; then
    echo "launcher-v$LAUNCHER_VERSION is not released: tag it and fill launcher.version before cutting a release" >&2
    exit 1
  fi
  echo "Warning: launcher-v$LAUNCHER_VERSION is not released — building the .app without the native launcher" >&2
elif [[ "$FETCH_LAUNCHER_STATUS" -ne 0 ]]; then
  echo "fetch_launcher.sh failed (exit $FETCH_LAUNCHER_STATUS)" >&2
  exit 1
fi

# Only bundle the splash art when there's actually a launcher to show it —
# the generated Contents/MacOS/SciQLop wrapper below falls back to a direct
# python3 exec otherwise.
if [[ -x "$MACOS_BIN/sciqlop-launcher" ]]; then
  cp "$SCIQLOP_ROOT/SciQLop/resources/splash.png" "$MACOS_BIN/splash.png"
fi

export PATH=$SAVED_PATH

# Node publishes macOS builds as `darwin-arm64` / `darwin-x64`; `uname -m`
# returns `arm64` / `x86_64`, so map the Intel name explicitly.
if [[ $ARCH == "x86_64" ]]; then NODE_ARCH=x64; else NODE_ARCH=$ARCH; fi
download_and_extract https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-darwin-$NODE_ARCH.tar.gz
rsync -aq $DIST/node-v$NODE_VERSION-darwin-$NODE_ARCH/* $DIST/SciQLop.app/Contents/Resources/usr/local/

python3 scripts/macos/make_bundle_portable.py $DIST/SciQLop.app

########################################
# Code signing — explicit inside-out, sequential.
#
# Why not `codesign --deep --force`:
#   `--force` on `--deep` does NOT propagate into nested code. When
#   codesign encounters an already-signed inner Mach-O during --deep
#   traversal it silently skips it. After `make_bundle_portable.py` runs
#   `install_name_tool` and `lipo -remove` on fat framework binaries,
#   their original (Qt Company) signatures are either invalidated or
#   partially retained. --deep --force won't replace them, so the runtime
#   fails with a Team ID mismatch at dlopen time, and notarization rejects
#   every one with "code object is not signed at all".
#
# Strategy: find EVERY Mach-O file by magic bytes and sign each one
# explicitly (hardened runtime + secure timestamp). Then seal the bundle
# wrappers inside-out: nested .app bundles deepest-first, then framework
# wrappers, then the outer SciQLop.app. --force is applied to each item
# directly, never via --deep.
#
# This covers items --deep --force misses:
#   - Qt framework inner Mach-Os (QtCore, QtGui, ...)
#   - dylibs and .so files
#   - Extensionless Mach-Os in PySide6/ (balsam, lupdate, qmlformat, ...)
#     and PySide6/Qt/libexec/ (rcc, uic, qmlcachegen, ...)
#   - Contents/Resources/opt/uv/uv
#   - Nested .app bundles: PySide6/{Assistant,Designer,Linguist}.app
#   - QtWebEngineProcess.app inside QtWebEngineCore.framework/Versions/A/Helpers/
#
# Sequential on purpose: keychain serializes codesign anyway, and
# apple-actions/import-codesign-certs keeps it unlocked for the whole job.
########################################

APP=$DIST/SciQLop.app
ENTITLEMENTS=$(realpath $HERE/entitlements.plist)

# Redact secrets from any string before printing. Substitutes the literal
# values of CODESIGN_IDENTITY, APPLE_ID, APPLE_ID_PWD, APPLE_TEAM_ID with
# fixed placeholders so a stray dump can't leak them.
redact() {
  local s="$1"
  [[ -n "${CODESIGN_IDENTITY:-}" ]] && s="${s//${CODESIGN_IDENTITY}/<CODESIGN_IDENTITY>}"
  [[ -n "${APPLE_ID:-}"          ]] && s="${s//${APPLE_ID}/<APPLE_ID>}"
  [[ -n "${APPLE_ID_PWD:-}"      ]] && s="${s//${APPLE_ID_PWD}/<APPLE_ID_PWD>}"
  [[ -n "${APPLE_TEAM_ID:-}"     ]] && s="${s//${APPLE_TEAM_ID}/<APPLE_TEAM_ID>}"
  printf '%s' "$s"
}

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  SIGN_ARGS=(--force --options runtime --timestamp -s "$CODESIGN_IDENTITY")
  EXEC_SIGN_ARGS=(--force --options runtime --timestamp --entitlements "$ENTITLEMENTS" -s "$CODESIGN_IDENTITY")
  IDENTITIES=$(security find-identity -v -p codesigning 2>&1 || true)
  if ! grep -q "Developer ID Application:" <<<"$IDENTITIES"; then
    echo "ERROR: no 'Developer ID Application:' certificate in keychain."
    echo "       The p12 in MACOS_CERTIFICATE must contain a Developer ID Application"
    echo "       certificate (not 'Mac Developer', 'Apple Development', etc)."
    echo "       Found $(grep -c 'valid identities found' <<<"$IDENTITIES" || true) identities (names redacted)."
    exit 1
  fi
  if ! grep -qF "$CODESIGN_IDENTITY" <<<"$IDENTITIES"; then
    echo "ERROR: CODESIGN_IDENTITY does not match any identity in the keychain."
    exit 1
  fi
  echo "Signing identity present and matched (value redacted)."
else
  echo "WARNING: No CODESIGN_IDENTITY set, using ad-hoc signing"
  SIGN_ARGS=(--force -s -)
  EXEC_SIGN_ARGS=(--force --entitlements "$ENTITLEMENTS" -s -)
fi

# Quiet codesign wrapper: swallow output on success, dump on failure.
# codesign normally prints "<file>: replacing existing signature" + "signed
# Mach-O ..." for each item — that's hundreds of lines per build. On failure
# we redact the signing identity from both args and output before printing.
quiet_codesign() {
  local out rc
  out=$(codesign "$@" 2>&1) && rc=0 || rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "ERROR: codesign failed (exit $rc) on file: ${!#}"
    redact "$out" | sed 's/^/  /'
    echo
    return $rc
  fi
}

# Canonical inside-out signing per Apple TN2206:
# - "all nested code must already be signed correctly" before signing the outer
# - For multi-version frameworks: "sign each specific version as opposed to
#   the whole framework", i.e. `codesign Foo.framework/Versions/A`, NOT
#   `codesign Foo.framework`. PySide6's Qt frameworks are all multi-version.
# - Do NOT use `--deep` (deprecated, "emergency repairs only").
# - Mach-O executables (MH_EXECUTE) need entitlements so hardened-runtime
#   library validation lets python3 dlopen PyPI wheels from the workspace
#   venv. Libraries/bundles must NOT carry entitlements — notarization
#   rejects entitlements on non-executable Mach-Os.
#
# Order:
#   1. Nested .app bundles, deepest first (inner Mach-Os, then .app wrapper)
#      — covers PySide6/{Designer,Linguist,Assistant}.app and the helper
#      QtWebEngineProcess.app inside QtWebEngineCore.framework/Versions/A/Helpers/
#   2. Loose Mach-Os outside any .app and outside any .framework
#      — python3, *.so bundles in PySide6/, plain dylibs in usr/local/lib/
#   3. Each *.framework/Versions/A directory, deepest first — canonical
#      multi-version-framework sign target. Codesign signs the version's
#      main binary and seals _CodeSignature/CodeResources with the
#      already-signed helpers.
#   4. Outer SciQLop.app

classify_macho() {
  local f="$1" desc
  desc=$(file -b "$f" 2>/dev/null)
  case "$desc" in
    *Mach-O*executable*) echo exec ;;
    *Mach-O*)            echo lib ;;
    *)                   echo none ;;
  esac
}

sign_macho() {
  local f="$1"
  case "$(classify_macho "$f")" in
    exec) quiet_codesign "${EXEC_SIGN_ARGS[@]}" "$f" && SIGNED_COUNT=$((SIGNED_COUNT+1)) ;;
    lib)  quiet_codesign "${SIGN_ARGS[@]}"      "$f" && SIGNED_COUNT=$((SIGNED_COUNT+1)) ;;
  esac
}

SIGNED_COUNT=0
NESTED_APPS=$(mktemp)
find "$APP/Contents" -type d -name "*.app" \
  | awk '{print length, $0}' | sort -rn | cut -d' ' -f2- > "$NESTED_APPS"
NESTED_APP_COUNT=$(wc -l <"$NESTED_APPS" | tr -d ' ')

echo "[1/4] Signing $NESTED_APP_COUNT nested .app bundle(s) inside-out..."
while IFS= read -r app; do
  while IFS= read -r -d '' f; do
    sign_macho "$f"
  done < <(find "$app" -type f -print0)
  quiet_codesign "${EXEC_SIGN_ARGS[@]}" "$app"
done < "$NESTED_APPS"
rm -f "$NESTED_APPS"

echo "[2/4] Signing loose Mach-Os outside .app/.framework..."
while IFS= read -r -d '' f; do
  sign_macho "$f"
done < <(find "$APP/Contents" \
  \( -type d \( -name "*.app" -o -name "*.framework" \) -prune \) \
  -o -type f -print0)

FRAMEWORK_VERSIONS=$(mktemp)
while IFS= read -r -d '' fw; do
  for ver in "$fw"/Versions/*; do
    [[ -d "$ver" && ! -L "$ver" ]] || continue
    [[ "$(basename "$ver")" == "Current" ]] && continue
    echo "$ver"
  done
done < <(find "$APP" -type d -name "*.framework" -print0) \
  | awk '{print length, $0}' | sort -rn | cut -d' ' -f2- > "$FRAMEWORK_VERSIONS"
FRAMEWORK_COUNT=$(wc -l <"$FRAMEWORK_VERSIONS" | tr -d ' ')

echo "[3/4] Signing $FRAMEWORK_COUNT framework version(s)..."
while IFS= read -r ver; do
  quiet_codesign "${SIGN_ARGS[@]}" "$ver"
done < "$FRAMEWORK_VERSIONS"
rm -f "$FRAMEWORK_VERSIONS"

echo "[4/4] Signing outer SciQLop.app..."
quiet_codesign "${EXEC_SIGN_ARGS[@]}" "$APP"
echo "Signed $SIGNED_COUNT Mach-O file(s) + $NESTED_APP_COUNT nested .app(s) + $FRAMEWORK_COUNT framework version(s) + outer .app"

if ! codesign --verify --strict "$APP" >/dev/null 2>&1; then
  echo "ERROR: signature verification failed; re-running verbose for diagnostics:"
  codesign --verify --deep --strict --verbose=2 "$APP" || true
  exit 1
fi
echo "Signature verified."

# Notarize the .app FIRST so we can staple the ticket onto the .app itself
# (not just onto the outer DMG). Otherwise, when the user drags the .app out
# of the DMG into /Applications, the staple stays on the DMG and Gatekeeper
# has to do an online ticket lookup on first launch, which is fragile.
# Notarytool helpers: never echo the credentials; redact stdout/stderr and
# capture to a file so failure dumps go through redact() too.
notary_submit() {
  local target="$1" out="$2"
  xcrun notarytool submit "$target" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PWD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait >"$out" 2>&1
}

notary_log() {
  local sub_id="$1"
  xcrun notarytool log "$sub_id" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PWD" \
    --team-id "$APPLE_TEAM_ID" 2>&1 || true
}

if [[ -n "$APPLE_ID" && -n "$APPLE_ID_PWD" && -n "$APPLE_TEAM_ID" ]]; then
  echo "Zipping .app for notarization submission..."
  APP_ZIP="$DIST/SciQLop-$ARCH-app.zip"
  ditto -c -k --keepParent "$APP" "$APP_ZIP"

  echo "Submitting .app to notarytool (this may take several minutes)..."
  NOTARY_OUT=$(mktemp)
  if ! notary_submit "$APP_ZIP" "$NOTARY_OUT"; then
    echo "ERROR: notarytool submit failed:"
    redact "$(cat "$NOTARY_OUT")" | sed 's/^/  /'
    rm -f "$NOTARY_OUT"
    exit 1
  fi
  if ! grep -q "status: Accepted" "$NOTARY_OUT"; then
    echo "ERROR: notarization not Accepted. Submission output:"
    redact "$(cat "$NOTARY_OUT")" | sed 's/^/  /'
    SUB_ID=$(grep -m1 "id:" "$NOTARY_OUT" | awk '{print $2}' || true)
    if [[ -n "$SUB_ID" ]]; then
      echo "Fetching notarytool log for $SUB_ID:"
      redact "$(notary_log "$SUB_ID")" | sed 's/^/  /'
    fi
    rm -f "$NOTARY_OUT"
    exit 1
  fi
  echo "Notarization Accepted."
  rm -f "$APP_ZIP" "$NOTARY_OUT"

  echo "Stapling notarization ticket to .app..."
  xcrun stapler staple "$APP" >/dev/null
  xcrun stapler validate "$APP" >/dev/null
  echo "Stapled and validated."
fi

cd $DIST
echo "Building DMG..."
# `create-dmg` auto-detects any codesigning identity in the keychain and
# attempts to sign the DMG. On PR builds CODESIGN_IDENTITY is empty and
# whatever it finds will fail with "The specified item could not be found
# in the keychain", but the DMG file is still produced. Tolerate the
# non-zero exit on that path and verify the DMG exists instead.
if [[ -n "$CODESIGN_IDENTITY" ]]; then
  create-dmg --overwrite --dmg-title=SciQLop SciQLop.app . >/dev/null
else
  create-dmg --overwrite --dmg-title=SciQLop SciQLop.app . >/dev/null || true
  ls SciQLop*.dmg >/dev/null 2>&1 || { echo "ERROR: create-dmg produced no DMG"; exit 1; }
fi
mv SciQLop*.dmg SciQLop-$ARCH.dmg

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  echo "Signing DMG..."
  quiet_codesign --force --options runtime -s "$CODESIGN_IDENTITY" SciQLop-$ARCH.dmg
fi

# DMG also gets notarized + stapled so the download itself is verifiable
# without having to mount it first.
if [[ -n "$APPLE_ID" && -n "$APPLE_ID_PWD" && -n "$APPLE_TEAM_ID" ]]; then
  echo "Submitting DMG to notarytool (this may take several minutes)..."
  DMG_NOTARY_OUT=$(mktemp)
  if ! notary_submit "SciQLop-$ARCH.dmg" "$DMG_NOTARY_OUT"; then
    echo "ERROR: DMG notarytool submit failed:"
    redact "$(cat "$DMG_NOTARY_OUT")" | sed 's/^/  /'
    rm -f "$DMG_NOTARY_OUT"
    exit 1
  fi
  if ! grep -q "status: Accepted" "$DMG_NOTARY_OUT"; then
    echo "ERROR: DMG notarization not Accepted. Submission output:"
    redact "$(cat "$DMG_NOTARY_OUT")" | sed 's/^/  /'
    SUB_ID=$(grep -m1 "id:" "$DMG_NOTARY_OUT" | awk '{print $2}' || true)
    if [[ -n "$SUB_ID" ]]; then
      echo "Fetching notarytool log for $SUB_ID:"
      redact "$(notary_log "$SUB_ID")" | sed 's/^/  /'
    fi
    rm -f "$DMG_NOTARY_OUT"
    exit 1
  fi
  echo "DMG notarization Accepted."
  rm -f "$DMG_NOTARY_OUT"
  xcrun stapler staple SciQLop-$ARCH.dmg >/dev/null
  echo "DMG stapled."
fi

cd -
