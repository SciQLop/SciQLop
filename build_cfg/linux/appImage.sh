#!/bin/bash
# guess using centos 7 as build host
yum install -y gtk3 openssl-devel.x86_64 ncurses-devel.x86_64 sqlite-devel.x86_64 tkinter.x86_64 readline-devel.x86_64 xz-devel.x86_64 gdbm-devel.x86_64 bzip2-devel.x86_64 tk-devel.x86_64 libffi-devel.x86_64 make
HERE="$(dirname "$(readlink -f "${0}")")"
SCIQLOP_SCR=$HERE/../../
SCIQLOP_BUILD=$SCIQLOP_SCR/build/
SCIQLOP_APPDIR=$SCIQLOP_BUILD/AppDir
mkdir $SCIQLOP_BUILD
cd $SCIQLOP_BUILD
# need to build python to easily install/relocate in AppImage
wget https://www.python.org/ftp/python/3.7.3/Python-3.7.3.tgz
tar -xf Python-3.7.3.tgz
cd Python-3.7.3
# Optimisation is damn slow maybe enabled later
./configure --enable-shared --prefix=/usr
make -j
DESTDIR=$SCIQLOP_BUILD/AppDir make install
cd ..
cp $HERE/AppRun $SCIQLOP_APPDIR/
chmod +x $SCIQLOP_APPDIR/AppRun
# Tweak to find custom python from build dir
sed "s|/usr|$SCIQLOP_APPDIR/usr|" -i $SCIQLOP_APPDIR/usr/lib/pkgconfig/python3.pc
LD_PRELOAD=$SCIQLOP_APPDIR/usr/lib/libpython3.7m.so.1.0 PATH=$SCIQLOP_APPDIR/usr/bin/:/usr/bin/ LD_LIBRARY_PATH=AppDir/usr/lib/:AppDir/usr/lib/python3.7/ $SCIQLOP_APPDIR/usr/bin/python3 $SCIQLOP_APPDIR/usr/bin/pip3 install speasy
LD_LIBRARY_PATH=$SCIQLOP_APPDIR/usr/lib/ PKG_CONFIG_PATH=$SCIQLOP_APPDIR/usr/lib/pkgconfig/:$PKG_CONFIG_PATH PATH=$SCIQLOP_APPDIR/usr/bin/:$PATH meson --prefix=/usr ..
ninja
DESTDIR=$SCIQLOP_APPDIR ninja install
cp -rf $SCIQLOP_APPDIR/usr/lib64/* $SCIQLOP_APPDIR/usr/lib/
rm -rf $SCIQLOP_APPDIR/usr/lib64/
wget https://github.com/probonopd/linuxdeployqt/releases/download/continuous/linuxdeployqt-continuous-x86_64.AppImage
chmod +x  linuxdeployqt-continuous-x86_64.AppImage && ./linuxdeployqt-continuous-x86_64.AppImage --appimage-extract
LD_LIBRARY_PATH=$SCIQLOP_APPDIR/usr/lib:$SCIQLOP_APPDIR/usr/lib/SciQLop/:$SCIQLOP_APPDIR/usr/lib/python3.7/site-packages/numpy/.libs/ ./squashfs-root/AppRun $SCIQLOP_APPDIR/usr/share/applications/*.desktop -appimage -extra-plugins=iconengines,platformthemes/libqgtk3.so
