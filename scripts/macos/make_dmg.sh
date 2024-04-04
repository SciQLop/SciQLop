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
export PATH=$HERE/usr/local/bin/
export LD_LIBRARY_PATH=$HERE/usr/local/lib
$HERE/usr/local/bin/python3 -m SciQLop.app
EOT

chmod +x $DIST/SciQLop.app/Contents/MacOS/SciQLop


export MACOSX_DEPLOYMENT_TARGET=11.0
curl https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tar.xz | tar xvz -C $DIST
cd $SCIQLOP_ROOT/dist/Python-3.10.14
./configure --enable-optimizations
make -j
make install DESTDIR=../SciQLop.app/Contents/MacOS 


$DIST/SciQLop.app/Contents/MacOS/usr/local/bin/python3 -m pip install $SCIQLOP_ROOT/

curl https://nodejs.org/dist/v20.12.1/node-v20.12.1-darwin-$ARCH.tar.gz | tar xvz -C $DIST
rsync -avhu $DIST/node-v20.12.1-darwin-$ARCH/* $DIST/SciQLop.app/Contents/MacOS/usr/local/

create-dmg --overwrite --dmg-title=SciQLop-$ARCH $DIST/SciQLop.app $DIST
