#!/usr/bin/env sh

set -e
SCRIPT_DIR=$(dirname "$0")
ABSOLUTE_SCRIPT_DIR=$(readlink -f "$SCRIPT_DIR")
SCIQLOP_ROOT=$ABSOLUTE_SCRIPT_DIR/../../

mkdir -p /tmp/sciqlop
cd /tmp/sciqlop

if [ ! -f ./python3.12.3-cp312-cp312-manylinux2014_x86_64.AppImage ]; then
    wget https://github.com/niess/python-appimage/releases/download/python3.12/python3.12.3-cp312-cp312-manylinux2014_x86_64.AppImage
    chmod +x python3.12.3-cp312-cp312-manylinux2014_x86_64.AppImage
fi
rm -rf ./squashfs-root
./python3.12.3-cp312-cp312-manylinux2014_x86_64.AppImage --appimage-extract
./squashfs-root/usr/bin/python3.12 -I -m pip install $SCIQLOP_ROOT
rm -f ./squashfs-root/AppRun
cp $ABSOLUTE_SCRIPT_DIR/AppRun ./squashfs-root/

curl https://nodejs.org/dist/v20.14.0/node-v20.14.0-linux-x64.tar.xz | tar -xJ -C /tmp/sciqlop
rsync -avhu /tmp/sciqlop/node-v20.14.0-linux-x64/* ./squashfs-root/usr/local/

if [ ! -f ./appimagetool-x86_64.AppImage ]; then
    wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

./appimagetool-x86_64.AppImage --appimage-extract-and-run -n ./squashfs-root/ SciQLop-x86_64.AppImage
mkdir -p $SCIQLOP_ROOT/dist
mv SciQLop-x86_64.AppImage* $SCIQLOP_ROOT/dist/

cd -

