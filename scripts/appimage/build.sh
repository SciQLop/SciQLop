#!/usr/bin/env sh

set -e
SCRIPT_DIR=$(dirname "$0")
ABSOLUTE_SCRIPT_DIR=$(readlink -f "$SCRIPT_DIR")
SCIQLOP_ROOT=$ABSOLUTE_SCRIPT_DIR/../../

mkdir -p /tmp/sciqlop
cd /tmp/sciqlop

PYTHON_APPIMAGE=python3.12.9-cp312-cp312-manylinux2014_x86_64.AppImage
PYTHON_VERSION=3.12


if [ ! -f ./$PYTHON_APPIMAGE ]; then
    wget https://github.com/niess/python-appimage/releases/download/python$PYTHON_VERSION/$PYTHON_APPIMAGE
    chmod +x $PYTHON_APPIMAGE
fi
rm -rf ./squashfs-root
./$PYTHON_APPIMAGE --appimage-extract
./squashfs-root/usr/bin/python$PYTHON_VERSION -I -m pip install $SCIQLOP_ROOT
if [ -z $RELEASE ]; then
  ./squashfs-root/usr/bin/python$PYTHON_VERSION -I -m pip install --upgrade git+https://github.com/SciQLop/speasy
fi

rm -f ./squashfs-root/AppRun
cp $ABSOLUTE_SCRIPT_DIR/AppRun ./squashfs-root/

curl https://nodejs.org/dist/v23.9.0/node-v23.9.0-linux-x64.tar.xz | tar -xJ -C /tmp/sciqlop
rsync -avhu /tmp/sciqlop/node-v23.9.0-linux-x64/* ./squashfs-root/usr/local/

if [ ! -f ./appimagetool-x86_64.AppImage ]; then
    wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

./appimagetool-x86_64.AppImage --appimage-extract-and-run -n ./squashfs-root/ SciQLop-x86_64.AppImage
mkdir -p $SCIQLOP_ROOT/dist
mv SciQLop-x86_64.AppImage* $SCIQLOP_ROOT/dist/

cd -

