#! /usr/bin/env bash
set -x
HERE=$(dirname $BASH_SOURCE)
SCIQLOP_ROOT=$HERE/../../
DIST=$SCIQLOP_ROOT/dist
ICONDIR=$DIST/SciQLop.app/Contents/Resources/SciQLop.iconset
ARCH=$(uname -m)

OPENSSL_VERSION=3.5.0
PYTHON_VERSION=3.12.10
NODE_VERSION=23.11.0
UV_VERSION=0.11.2

mkdir $DIST

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
    curl -L $1 -o $DESTFILE
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
  curl -L -o $DIST/uv.tar.gz "$UV_URL"
fi

tar -xzf $DIST/uv.tar.gz -C $DIST
cp $DIST/uv-*/uv $DIST/SciQLop.app/Contents/Resources/opt/uv/
chmod +x $DIST/SciQLop.app/Contents/Resources/opt/uv/uv

UV_BIN=$DIST/SciQLop.app/Contents/Resources/opt/uv/uv

########################################
# Install SciQLop using uv
########################################

$UV_BIN pip install --reinstall --no-cache --python $PYTHON_BIN "$SCIQLOP_ROOT/"

########################################
# Plugin dependencies
########################################

PLUGIN_DEPENDENCIES=$($PYTHON_BIN -I $SCIQLOP_ROOT/scripts/list_plugins_dependencies.py $SCIQLOP_ROOT/SciQLop/plugins)
if [[ -n "$PLUGIN_DEPENDENCIES" ]]; then
  $UV_BIN pip install --python $PYTHON_BIN $PLUGIN_DEPENDENCIES
fi

if [[ $ARCH == "x86_64" ]]; then
  cp $(brew --prefix gettext)/lib/libintl.8.dylib $DIST/SciQLop.app/Contents/Resources/usr/local/lib/
  install_name_tool -change /usr/local/opt/gettext/lib/libintl.8.dylib @loader_path/lib/libintl.8.dylib $DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3
fi

########################################
# Dev speasy override
########################################

if [[ -z $RELEASE ]]; then
  $UV_BIN pip install --python $PYTHON_BIN --upgrade git+https://github.com/SciQLop/speasy
fi

export PATH=$SAVED_PATH

download_and_extract https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-darwin-$ARCH.tar.gz
rsync -avhu $DIST/node-v$NODE_VERSION-darwin-$ARCH/* $DIST/SciQLop.app/Contents/Resources/usr/local/

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

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  SIGN_ARGS=(--force --options runtime --timestamp -s "$CODESIGN_IDENTITY")
  EXEC_SIGN_ARGS=(--force --options runtime --timestamp --entitlements "$ENTITLEMENTS" -s "$CODESIGN_IDENTITY")
  echo "Pre-flight: verifying signing identity is in keychain..."
  security find-identity -v -p codesigning
  if ! security find-identity -v -p codesigning | grep -q "Developer ID Application:"; then
    echo "ERROR: no 'Developer ID Application:' certificate in keychain."
    echo "       The p12 in MACOS_CERTIFICATE must contain a Developer ID Application"
    echo "       certificate (not 'Mac Developer', 'Apple Development', etc)."
    echo "       Notarization will reject any signature made with a non-Developer-ID cert."
    exit 1
  fi
  if ! security find-identity -v -p codesigning | grep -qF "$CODESIGN_IDENTITY"; then
    echo "ERROR: CODESIGN_IDENTITY does not match any identity in the keychain."
    echo "       Expected substring: $CODESIGN_IDENTITY"
    exit 1
  fi
else
  echo "WARNING: No CODESIGN_IDENTITY set, using ad-hoc signing"
  SIGN_ARGS=(--force -s -)
  EXEC_SIGN_ARGS=(--force --entitlements "$ENTITLEMENTS" -s -)
fi

# Mach-O executables (MH_EXECUTE) need entitlements so hardened-runtime
# library validation lets python3 dlopen third-party-signed PyPI wheels
# (PySide6, shiboken6, numpy, ...). Libraries (.dylib, .so bundles) and
# framework inner Mach-Os must NOT carry entitlements — Apple notarization
# rejects entitlements on non-executable Mach-Os.
#
# `file -b` distinguishes them: executables show "executable", dylibs show
# "shared library", Python .so extensions show "bundle".
echo "Collecting Mach-O binaries in $APP..."
# Skip Mach-Os inside *.framework/ — the framework wrapper sign pass below
# signs them as part of the framework bundle. Signing framework inner
# binaries directly AND then re-sealing the framework wrapper corrupts
# signatures for frameworks that contain nested .app helpers
# (notably QtWebEngineCore.framework/Versions/A/Helpers/QtWebEngineProcess.app),
# which makes notarytool reject the inner binary as "signature is invalid".
# Same logic for nested .app bundles — handled in their own pass below.
MACHO_EXEC_LIST=$(mktemp)
MACHO_LIB_LIST=$(mktemp)
while IFS= read -r -d '' f; do
  rel="${f#$APP/}"
  case "$rel" in
    *.framework/*) continue ;;
    *.app/*) continue ;;
  esac
  desc=$(file -b "$f" 2>/dev/null)
  case "$desc" in
    *Mach-O*executable*) printf '%s\0' "$f" >> "$MACHO_EXEC_LIST" ;;
    *Mach-O*) printf '%s\0' "$f" >> "$MACHO_LIB_LIST" ;;
  esac
done < <(find "$APP" -type f -print0)

EXEC_COUNT=$(tr -cd '\0' < "$MACHO_EXEC_LIST" | wc -c | tr -d ' ')
LIB_COUNT=$(tr -cd '\0' < "$MACHO_LIB_LIST" | wc -c | tr -d ' ')

echo "Signing $LIB_COUNT Mach-O libraries (no entitlements)..."
xargs -0 -n 50 codesign "${SIGN_ARGS[@]}" < "$MACHO_LIB_LIST"

echo "Signing $EXEC_COUNT Mach-O executables (with entitlements)..."
xargs -0 -n 50 codesign "${EXEC_SIGN_ARGS[@]}" < "$MACHO_EXEC_LIST"

rm -f "$MACHO_EXEC_LIST" "$MACHO_LIB_LIST"

echo "Signing nested .app bundles (deepest first, with entitlements)..."
find "$APP" -mindepth 1 -type d -name "*.app" \
  | awk '{print length, $0}' | sort -rn | cut -d' ' -f2- \
  | while IFS= read -r app; do
      codesign "${EXEC_SIGN_ARGS[@]}" "$app"
    done

echo "Signing framework wrappers (deepest first, no entitlements)..."
find "$APP" -type d -name "*.framework" \
  | awk '{print length, $0}' | sort -rn | cut -d' ' -f2- \
  | while IFS= read -r fw; do
      codesign "${SIGN_ARGS[@]}" "$fw"
    done

echo "Signing outer app bundle (with entitlements)..."
codesign "${EXEC_SIGN_ARGS[@]}" "$APP"

echo "Verifying signature..."
codesign --verify --deep --strict --verbose=2 "$APP" || {
  echo "ERROR: signature verification failed"
  exit 1
}

# Notarize the .app FIRST so we can staple the ticket onto the .app itself
# (not just onto the outer DMG). Otherwise, when the user drags the .app out
# of the DMG into /Applications, the staple stays on the DMG and Gatekeeper
# has to do an online ticket lookup on first launch, which is fragile.
if [[ -n "$APPLE_ID" && -n "$APPLE_ID_PWD" && -n "$APPLE_TEAM_ID" ]]; then
  echo "Zipping .app for notarization submission..."
  APP_ZIP="$DIST/SciQLop-$ARCH-app.zip"
  ditto -c -k --keepParent "$APP" "$APP_ZIP"

  echo "Submitting .app to notarytool..."
  NOTARY_OUT=$(mktemp)
  if ! xcrun notarytool submit "$APP_ZIP" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_ID_PWD" \
        --team-id "$APPLE_TEAM_ID" \
        --wait 2>&1 | tee "$NOTARY_OUT"; then
    echo "ERROR: notarytool submit failed"
    cat "$NOTARY_OUT"
    exit 1
  fi
  if ! grep -q "status: Accepted" "$NOTARY_OUT"; then
    echo "ERROR: notarization not Accepted. Fetching log..."
    SUB_ID=$(grep -m1 "id:" "$NOTARY_OUT" | awk '{print $2}')
    if [[ -n "$SUB_ID" ]]; then
      xcrun notarytool log "$SUB_ID" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_ID_PWD" \
        --team-id "$APPLE_TEAM_ID" || true
    fi
    exit 1
  fi
  rm -f "$APP_ZIP" "$NOTARY_OUT"

  echo "Stapling notarization ticket to .app..."
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
fi

cd $DIST
create-dmg --overwrite --dmg-title=SciQLop SciQLop.app .
mv SciQLop*.dmg SciQLop-$ARCH.dmg

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  codesign --force --verbose --options runtime -s "$CODESIGN_IDENTITY" SciQLop-$ARCH.dmg
fi

# DMG also gets notarized + stapled so the download itself is verifiable
# without having to mount it first.
if [[ -n "$APPLE_ID" && -n "$APPLE_ID_PWD" && -n "$APPLE_TEAM_ID" ]]; then
  echo "Submitting DMG to notarytool..."
  DMG_NOTARY_OUT=$(mktemp)
  if ! xcrun notarytool submit SciQLop-$ARCH.dmg \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_ID_PWD" \
        --team-id "$APPLE_TEAM_ID" \
        --wait 2>&1 | tee "$DMG_NOTARY_OUT"; then
    echo "ERROR: DMG notarytool submit failed"
    exit 1
  fi
  if ! grep -q "status: Accepted" "$DMG_NOTARY_OUT"; then
    echo "ERROR: DMG notarization not Accepted"
    SUB_ID=$(grep -m1 "id:" "$DMG_NOTARY_OUT" | awk '{print $2}')
    if [[ -n "$SUB_ID" ]]; then
      xcrun notarytool log "$SUB_ID" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_ID_PWD" \
        --team-id "$APPLE_TEAM_ID" || true
    fi
    exit 1
  fi
  rm -f "$DMG_NOTARY_OUT"
  xcrun stapler staple SciQLop-$ARCH.dmg
fi

cd -
