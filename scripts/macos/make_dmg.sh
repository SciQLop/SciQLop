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
export PATH=$HERE/../Resources/usr/local/bin/:/usr/bin:/bin:/usr/sbin:/sbin
export QT_PATH=$($HERE/../Resources/usr/local/bin/python3 -c "import PySide6,os;print(os.path.dirname(PySide6.__file__));")/Qt
export LD_LIBRARY_PATH=$HERE/../Resources/usr/local/lib
export DYLD_LIBRARY_PATH=$HERE/../Resources/usr/local/lib:$HERE/usr/local/bin/:$QT_PATH/lib
export QT_PLUGIN_PATH=$QT_PATH/plugins
export QTWEBENGINE_CHROMIUM_FLAGS="--single-process"
export SSL_CERT_FILE=$($HERE/../Resources/usr/local/bin/python3 -m certifi)
export REQUESTS_CA_BUNDLE=${SSL_CERT_FILE}
export SCIQLOP_BUNDLED="1"
$HERE/../Resources/usr/local/bin/python3 -m SciQLop.app
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


$DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3 -m pip install $SCIQLOP_ROOT/

if [[ -z $RELEASE ]]; then
  $DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3 -m pip install --upgrade git+https://github.com/SciQLop/speasy
fi

export PATH=$SAVED_PATH

download_and_extract https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-darwin-$ARCH.tar.gz
rsync -avhu $DIST/node-v$NODE_VERSION-darwin-$ARCH/* $DIST/SciQLop.app/Contents/Resources/usr/local/

python3 scripts/macos/make_bundle_portable.py $DIST/SciQLop.app

codesign --force --deep --verbose -s - $DIST/SciQLop.app

cd $DIST
create-dmg --overwrite --dmg-title=SciQLop SciQLop.app .
mv SciQLop*.dmg SciQLop-$ARCH.dmg
cd -
