#! /usr/bin/env bash
set -x
HERE=$(dirname $BASH_SOURCE)
SCIQLOP_ROOT=$HERE/../../
DIST=$SCIQLOP_ROOT/dist
ICONDIR=$DIST/SciQLop.app/Contents/Resources/SciQLop.iconset
ARCH=$(uname -m)

mkdir $DIST

mkdir -p $DIST/SciQLop.app/Contents/MacOS
mkdir -p $ICONDIR

for SIZE in 16 32 64 128 256 512; do
sips -z $SIZE $SIZE $SCIQLOP_ROOT/SciQLop/resources/icons/SciQLop.png --out $ICONDIR/icon_${SIZE}x${SIZE}.png ;
done

for SIZE in 32 64 256 512; do
sips -z $SIZE $SIZE $SCIQLOP_ROOT/SciQLop/resources/icons/SciQLop.png --out $ICONDIR/icon_$(expr $SIZE / 2)x$(expr $SIZE / 2)x2.png ;
done

iconutil -c icns -o $DIST/SciQLop.app/Contents/Resources/SciQLop.icns $ICONDIR
rm -rf $ICONDIR

cat <<'EOT' >> $DIST/SciQLop.app/Contents/Info.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>SciQLop</string>
  <key>CFBundleIdentifier</key>
	<string>com.LPP.SciQLop</string>
	<key>CFBundleName</key>
	<string>SciQLop</string>
	<key>CFBundleVersion</key>
	<string>0.6</string>
  <key>CFBundleIconFile</key>
  <string>SciQLop.icns</string>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOT

cat <<'EOT' >> $DIST/SciQLop.app/Contents/MacOS/SciQLop
#! /usr/bin/env bash
export HERE=$(dirname $BASH_SOURCE)
export PATH=$HERE/../Resources/usr/local/bin/:/usr/bin:/bin:/usr/sbin:/sbin
export QT_PATH=$($HERE/../Resources/usr/local/bin/python3 -c "import PySide6,os;print(os.path.dirname(PySide6.__file__));")/Qt
export LD_LIBRARY_PATH=$HERE/../Resources/usr/local/lib:$HERE/../Resources/usr/local/extra-lib
export DYLD_LIBRARY_PATH=$HERE/../Resources/usr/local/lib:$HERE/usr/local/bin/:$QT_PATH/lib:$HERE/../Resources/usr/local/extra-lib
export QT_PLUGIN_PATH=$QT_PATH/plugins
export QTWEBENGINE_CHROMIUM_FLAGS="--single-process"
export SCIQLOP_BUNDLED="1"
$HERE/../Resources/usr/local/bin/python3 -m SciQLop.app
EOT

chmod +x $DIST/SciQLop.app/Contents/MacOS/SciQLop


export MACOSX_DEPLOYMENT_TARGET=11.0
curl https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tar.xz | tar xvz -C $DIST
cd $SCIQLOP_ROOT/dist/Python-3.12.4
./configure --enable-optimizations
make -j
make install DESTDIR=../SciQLop.app/Contents/Resources
cd -


$DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3 -m pip install $SCIQLOP_ROOT/

if [[ -z $RELEASE ]]; then
  $DIST/SciQLop.app/Contents/Resources/usr/local/bin/python3 -m pip install --upgrade git+https://github.com/SciQLop/speasy
fi

curl https://nodejs.org/dist/v20.12.1/node-v20.12.1-darwin-$ARCH.tar.gz | tar xvz -C $DIST
rsync -avhu $DIST/node-v20.12.1-darwin-$ARCH/* $DIST/SciQLop.app/Contents/Resources/usr/local/

if [[ -f /usr/local/lib/libintl.8.dylib ]]; then
  cp /usr/local/lib/libintl.8.dylib $DIST/SciQLop.app/Contents/Resources/usr/local/lib/
fi

cd $DIST
for lib in $(find ./SciQLop.app -type f -perm +a=x | grep -vi 'SciQLopPlots\|pyside\|shiboken' | grep '\.so'); do
  dylibbundler -cd -b -x $lib -d ./SciQLop.app/Contents/Resources/usr/local/extra-lib
done
cd -

exec_files=$(find $DIST/SciQLop.app -type f -perm +a=x)
if [[ $ARCH == "arm64" ]]; then
  export arch_to_remove="x86_64"
else
  export arch_to_remove="arm64"
fi

for e_file in $exec_files; do
  if [[ $(file $e_file) == *Mach-O* ]]; then
    lipo -remove $arch_to_remove -output $e_file $e_file
  fi
done



codesign --force --deep --verbose -s - $DIST/SciQLop.app

cd $DIST
create-dmg --overwrite --dmg-title=SciQLop SciQLop.app .
mv SciQLop*.dmg SciQLop-$ARCH.dmg
cd -
