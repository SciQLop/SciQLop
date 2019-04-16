#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
mkdir build
cd build
mkdir -p $(pwd)/AppDir/usr
cp $HERE/AppRun $(pwd)/AppDir/
chmod +x $(pwd)/AppDir/AppRun
virtualenv --always-copy  --relocatable  -p python3 $(pwd)/AppDir/usr
$(pwd)/AppDir/usr/bin/pip3 install git+https://github.com/jeandet/spwc
meson --prefix=/usr ..
ninja
DESTDIR=$(pwd)/AppDir ninja install
mv AppDir/usr/lib64 AppDir/usr/lib
wget https://github.com/probonopd/linuxdeployqt/releases/download/continuous/linuxdeployqt-continuous-x86_64.AppImage
chmod +x  linuxdeployqt-continuous-x86_64.AppImage && ./linuxdeployqt-continuous-x86_64.AppImage --appimage-extract
LD_LIBRARY_PATH=AppDir/usr/lib/:AppDir/usr/lib/SciQLop/:$(python3-config --prefix)/lib64 ./squashfs-root/AppRun AppDir/usr/share/applications/*.desktop -appimage -extra-plugins=iconengines,platformthemes/libqgtk3.so -ignore-glob=$(pwd)/AppDir/usr/lib/python3.6/site-packages/*
