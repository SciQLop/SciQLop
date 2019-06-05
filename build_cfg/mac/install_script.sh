#!/bin/bash

mkdir -p ${MESON_INSTALL_PREFIX}/Contents/Frameworks
mv ${MESON_INSTALL_PREFIX}/lib/*plugin* ${MESON_INSTALL_PREFIX}/Contents/MacOS
macdeployqt ${MESON_INSTALL_PREFIX} -verbose=3 -executable=/tmp/SciQLOP.app/Contents/MacOS/sciqlop
python_lib_path=`otool -L /tmp/SciQLOP.app/Contents/MacOS/sciqlop | grep -i python | cut -d' ' -f1`
stdcpp_lib_path=`otool -L /tmp/SciQLOP.app/lib/pysciqlopcore.*.so | grep -i stdc++ | cut -d' ' -f1`
install_name_tool -change @rpath/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/Versions/5/QtCore /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change @rpath/QtPrintSupport.framework/Versions/5/QtPrintSupport @executable_path/../Frameworks/QtPrintSupport.framework/Versions/5/QtPrintSupport /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change @rpath/QtGui.framework/Versions/5/QtGui @executable_path/../Frameworks/QtGui.framework/Versions/5/QtGui /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change @rpath/QtWidgets.framework/Versions/5/QtWidgets @executable_path/../Frameworks/QtWidgets.framework/Versions/5/QtWidgets /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change @rpath/QtNetwork.framework/Versions/5/QtNetwork @executable_path/../Frameworks/QtNetwork.framework/Versions/5/QtNetwork /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change @rpath/QtSvg.framework/Versions/5/QtSvg @executable_path/../Frameworks/QtSvg.framework/Versions/5/QtSvg /tmp/SciQLOP.app/Contents/MacOS/sciqlop
install_name_tool -change $python_lib_path @executable_path/../.Python /tmp/SciQLOP.app/Contents/MacOS/sciqlop

install_name_tool -change @rpath/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/Versions/5/QtCore /tmp/SciQLOP.app/lib/pysciqlopcore.*.so
install_name_tool -change @rpath/QtNetwork.framework/Versions/5/QtNetwork @executable_path/../Frameworks/QtNetwork.framework/Versions/5/QtNetwork /tmp/SciQLOP.app/lib/pysciqlopcore.*.so
install_name_tool -change @rpath/QtNetwork.framework/Versions/5/QtNetwork @executable_path/../Frameworks/QtNetwork.framework/Versions/5/QtNetwork /tmp/SciQLOP.app/lib/pysciqlopcore.*.so
install_name_tool -change $python_lib_path @executable_path/../.Python /tmp/SciQLOP.app/lib/pysciqlopcore.*.so
install_name_tool -change $stdcpp_lib_path @executable_path/../Frameworks/libstdc++.*.dylib /tmp/SciQLOP.app/lib/pysciqlopcore.*.so
