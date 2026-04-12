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
# Code signing — inside-out, sequential.
# `codesign --deep` is deprecated. We walk the bundle from leaves to root so each
# enclosing container is signed after its contents. Sequential on purpose:
# the keychain serializes codesign operations and parallelism just hangs on lock
# contention. apple-actions/import-codesign-certs in the workflow keeps the
# keychain unlocked for the whole job so we don't need per-call unlock dances.
########################################

APP=$DIST/SciQLop.app

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  SIGN_ARGS=(--force --options runtime --timestamp -s "$CODESIGN_IDENTITY")
else
  echo "WARNING: No CODESIGN_IDENTITY set, using ad-hoc signing"
  SIGN_ARGS=(--force -s -)
fi

sign_all() {
  xargs -0 -n 50 codesign "${SIGN_ARGS[@]}"
}

echo "Signing dylibs and .so files..."
find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 | sign_all

echo "Signing frameworks..."
find "$APP" -type d -name "*.framework" -print0 | sign_all

echo "Signing executables..."
find "$APP/Contents/MacOS" -type f -perm +111 -print0 | sign_all
if [[ -d "$APP/Contents/Resources/usr/local/bin" ]]; then
  find "$APP/Contents/Resources/usr/local/bin" -type f -perm +111 -print0 | sign_all
fi

echo "Signing app bundle..."
codesign "${SIGN_ARGS[@]}" "$APP"

cd $DIST
create-dmg --overwrite --dmg-title=SciQLop SciQLop.app .
mv SciQLop*.dmg SciQLop-$ARCH.dmg

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  codesign --force --verbose --options runtime -s "$CODESIGN_IDENTITY" SciQLop-$ARCH.dmg
fi

if [[ -n "$APPLE_ID" && -n "$APPLE_ID_PWD" && -n "$APPLE_TEAM_ID" ]]; then
  xcrun notarytool submit SciQLop-$ARCH.dmg \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PWD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait
  xcrun stapler staple SciQLop-$ARCH.dmg
fi

cd -
