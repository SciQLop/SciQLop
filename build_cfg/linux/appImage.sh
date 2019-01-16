#!/bin/bash
mkdir build
cd build
meson --prefix=/usr ..
ninja
DESTDIR=AppDir ninja install
wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x linuxdeploy-x86_64.AppImage
LD_LIBRARY_PATH=AppDir/usr/lib/ ./linuxdeploy-x86_64.AppImage --appdir AppDir
mv ./AppDir/usr/lib64/*.so ./AppDir/usr/lib/
mv ./AppDir/usr/lib/*plugin.so ./AppDir/usr/bin/
LD_LIBRARY_PATH=AppDir/usr/lib/ ./linuxdeploy-x86_64.AppImage --appdir AppDir --output appimage