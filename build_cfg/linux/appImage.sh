#!/bin/bash
mkdir build
cd build
meson --prefix=/usr ..
ninja
DESTDIR=AppDir ninja install
mv AppDir/usr/lib64 AppDir/usr/lib
mv AppDir/usr/lib/*plugin.so AppDir/usr/bin/
wget https://github.com/probonopd/linuxdeployqt/releases/download/continuous/linuxdeployqt-continuous-x86_64.AppImage
chmod +x  linuxdeployqt-continuous-x86_64.AppImage && ./linuxdeployqt-continuous-x86_64.AppImage --appimage-extract
LD_LIBRARY_PATH=AppDir/usr/lib64/ ./squashfs-root/AppRun AppDir/usr/share/applications/*.desktop -appimage
