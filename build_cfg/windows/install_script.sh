#!/bin/bash

mkdir -p ${MESON_INSTALL_PREFIX}/plugins
mv ${MESON_INSTALL_PREFIX}/bin/*plugin*.dll ${MESON_INSTALL_PREFIX}/plugins/
mv ${MESON_INSTALL_PREFIX}/lib64/*.dll ${MESON_INSTALL_PREFIX}/
mv ${MESON_INSTALL_PREFIX}/bin/* ${MESON_INSTALL_PREFIX}/

cp /usr/x86_64-w64-mingw32/sys-root/mingw/lib/qt5/plugins/platforms/qwindows.dll ${MESON_INSTALL_PREFIX}/
cp /usr/x86_64-w64-mingw32/sys-root/mingw/lib/qt5/plugins/imageformats/*.dll ${MESON_INSTALL_PREFIX}/

peldd ${MESON_INSTALL_PREFIX}/sciqlop.exe -a -w libsciqlopcore.dll -w libsciqlopgui.dll -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/libsciqlopcore.dll -a  -w libsciqlopgui.dll -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/libsciqlopgui.dll -a -w libsciqlopcore.dll -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/qwindows.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true

peldd ${MESON_INSTALL_PREFIX}/qjp2.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/qjpeg.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/qsvg.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/qtiff.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/qwebp.dll -a -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/plugins/libamdaplugin.dll -a -w libsciqlopgui.dll -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true
peldd ${MESON_INSTALL_PREFIX}/plugins/libmockplugin.dll -a -w libsciqlopgui.dll -w libsciqlopcore.dll  -w dwmapi.dll -w UxTheme.dll -w CRYPT32.dll -w DNSAPI.dll -w IPHLPAPI.DLL -w comdlg32.dll -w WINSPOOL.DRV  -w IMM32.dll | xargs cp -t ${MESON_INSTALL_PREFIX}/ || true

rm ${MESON_INSTALL_PREFIX}/bin/*plugin*.dll

rm -r ${MESON_INSTALL_PREFIX}/bin ${MESON_INSTALL_PREFIX}/lib64
