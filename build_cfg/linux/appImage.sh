#!/bin/bash
# guess using centos 7 as build host
yum install -y gtk3 openssl-devel.x86_64 ncurses-devel.x86_64 sqlite-devel.x86_64 tkinter.x86_64 readline-devel.x86_64 xz-devel.x86_64 gdbm-devel.x86_64 bzip2-devel.x86_64 tk-devel.x86_64 libffi-devel.x86_64 make
HERE="$(dirname "$(readlink -f "${0}")")"
mkdir build
cd build
# need to build python to easily install/relocate in AppImage
wget https://www.python.org/ftp/python/3.7.3/Python-3.7.3.tgz
tar -xf Python-3.7.3.tgz
cd Python-3.7.3
# Optimisation is damn slow maybe enabled later
./configure --enable-shared --prefix=/usr
make -j
DESTDIR=$(pwd)/../AppDir make install
cd ..
cp $HERE/AppRun $(pwd)/AppDir/
chmod +x $(pwd)/AppDir/AppRun
# Tweak to find custom python from build dir
sed s/\\/usr/\\/SciQLop\\/build\\/AppDir\\/usr/ -i AppDir/usr/lib/pkgconfig/python3.pc
LD_PRELOAD=$(pwd)/AppDir/usr/lib/libpython3.7m.so.1.0 PATH=$(pwd)/AppDir/usr/bin/:/usr/bin/ LD_LIBRARY_PATH=AppDir/usr/lib/:AppDir/usr/lib/python3.7/ $(pwd)/AppDir/usr/bin/python3 $(pwd)/AppDir/usr/bin/pip3 install git+https://github.com/jeandet/spwc
LD_LIBRARY_PATH=AppDir/usr/lib/ PKG_CONFIG_PATH=./AppDir/usr/lib/pkgconfig/:$PKG_CONFIG_PATH PATH=./AppDir/usr/bin/:$PATH meson --prefix=/usr ..
ninja
DESTDIR=$(pwd)/AppDir ninja install
cp -r -t AppDir/usr/lib64/* AppDir/usr/lib/
rm -rf AppDir/usr/lib64/
wget https://github.com/probonopd/linuxdeployqt/releases/download/continuous/linuxdeployqt-continuous-x86_64.AppImage
chmod +x  linuxdeployqt-continuous-x86_64.AppImage && ./linuxdeployqt-continuous-x86_64.AppImage --appimage-extract
LD_LIBRARY_PATH=AppDir/usr/lib:AppDir/usr/lib/SciQLop/:AppDir/usr/lib/python3.7/site-packages/numpy/.libs/ ./squashfs-root/AppRun AppDir/usr/share/applications/*.desktop -appimage -extra-plugins=iconengines,platformthemes/libqgtk3.so
