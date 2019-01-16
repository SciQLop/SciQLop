#!/bin/bash
mkdir build
cd build
meson --prefix=/usr ..
ninja
DESTDIR=AppDir ninja install
wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x linuxdeploy-x86_64.AppImage
./linuxdeploy-x86_64.AppImage --appimage-extract
LD_LIBRARY_PATH=AppDir/usr/lib/ ./squashfs-root/AppRun --appdir AppDir
mv ./AppDir/usr/lib64/*.so ./AppDir/usr/lib/
mv ./AppDir/usr/lib/*plugin.so ./AppDir/usr/bin/
LD_LIBRARY_PATH=AppDir/usr/lib/ ./squashfs-root/AppRun --appdir AppDir --output appimage