#! /usr/bin/env bash
set -eo pipefail
HERE=$(dirname $BASH_SOURCE)
SCIQLOP_ROOT=$HERE/../../
DIST=$SCIQLOP_ROOT/dist
ICONDIR=$DIST/SciQLop.app/Contents/Resources/SciQLop.iconset
ARCH=$(uname -m)

OPENSSL_VERSION=3.5.0
PYTHON_VERSION=3.12.10
NODE_VERSION=23.11.0
UV_VERSION=0.11.2

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

cat <<'EOT' >> $DIST/SciQLop.app/Contents/MacOS/SciQLop
#! /usr/bin/env bash
export HERE=$(dirname $BASH_SOURCE)
export RESOURCES=$HERE/../Resources
export PATH=$RESOURCES/opt/uv:$RESOURCES/usr/local/bin/:/usr/bin:/bin:/usr/sbin:/sbin
export QT_PATH=$($RESOURCES/usr/local/bin/python3 -c "import PySide6,os;print(os.path.dirname(PySide6.__file__));")/Qt
export LD_LIBRARY_PATH=$RESOURCES/usr/local/lib
export DYLD_LIBRARY_PATH=$RESOURCES/usr/local/lib:$RESOURCES/usr/local/bin/:$QT_PATH/lib
export QT_PLUGIN_PATH=$QT_PATH/plugins
export QTWEBENGINE_CHROMIUM_FLAGS="--single-process"
export SSL_CERT_FILE=$($RESOURCES/usr/local/bin/python3 -m certifi)
export REQUESTS_CA_BUNDLE=${SSL_CERT_FILE}
export SCIQLOP_BUNDLED="1"
$RESOURCES/usr/local/bin/python3 -m SciQLop.app
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

download_and_extract  https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz

cd $DIST/openssl-$OPENSSL_VERSION
if [[ $ARCH == "arm64" ]]; then
  ./Configure darwin64-arm64-cc --prefix=$PREFIX_ABS > ../openssl-configure.log
else
  ./Configure darwin64-x86_64-cc --prefix=$PREFIX_ABS > ../openssl-configure.log
fi
make -j > ../openssl-make.log
make install install_sw > ../openssl-install.log # skip install_docs
cd -

export PKG_CONFIG_PATH=$(realpath $DIST/SciQLop.app/Contents/Resources/usr/local/lib/pkgconfig)


download_and_extract https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz
cd $SCIQLOP_ROOT/dist/Python-$PYTHON_VERSION
./configure --enable-optimizations --with-openssl=$PREFIX_ABS --prefix=$PREFIX_ABS > ../python-configure.log
make -j > ../python-make.log
make install  > ../python-install.log
cd -

########################################
# Fetch uv standalone
########################################

PYTHON_BIN=$DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3

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
# Install SciQLop using uv
########################################

echo "Installing SciQLop into bundle..."
$UV_BIN pip install -q --reinstall --no-cache --python $PYTHON_BIN "$SCIQLOP_ROOT/"

########################################
# Plugin dependencies
########################################

PLUGIN_DEPENDENCIES=$($PYTHON_BIN -I $SCIQLOP_ROOT/scripts/list_plugins_dependencies.py $SCIQLOP_ROOT/SciQLop/plugins)
if [[ -n "$PLUGIN_DEPENDENCIES" ]]; then
  echo "Installing plugin dependencies: $PLUGIN_DEPENDENCIES"
  $UV_BIN pip install -q --python $PYTHON_BIN $PLUGIN_DEPENDENCIES
fi

if [[ $ARCH == "x86_64" ]]; then
  cp $(brew --prefix gettext)/lib/libintl.8.dylib $DIST/SciQLop.app/Contents/Resources/usr/local/lib/
  install_name_tool -change /usr/local/opt/gettext/lib/libintl.8.dylib @loader_path/lib/libintl.8.dylib $DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3
fi

########################################
# Dev speasy override
########################################

if [[ -z $RELEASE ]]; then
  $UV_BIN pip install -q --python $PYTHON_BIN --upgrade git+https://github.com/SciQLop/speasy
fi

export PATH=$SAVED_PATH

download_and_extract https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-darwin-$ARCH.tar.gz
rsync -aq $DIST/node-v$NODE_VERSION-darwin-$ARCH/* $DIST/SciQLop.app/Contents/Resources/usr/local/

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
# `create-dmg` auto-detects any codesigning identity in the keychain and tries
# to sign the DMG. On PR builds we have no CODESIGN_IDENTITY (ad-hoc app
# signing), so force --identity=NONE to skip DMG signing entirely.
if [[ -n "$CODESIGN_IDENTITY" ]]; then
  create-dmg --overwrite --dmg-title=SciQLop SciQLop.app . >/dev/null
else
  create-dmg --overwrite --identity=NONE --dmg-title=SciQLop SciQLop.app . >/dev/null
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
