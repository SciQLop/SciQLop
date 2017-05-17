@echo off
echo Setting up environment for Qt usage...

set QT_QMAKE_PATH=C:\Qt\5.8\mingw53_32\bin
set QT_MINGW_PATH=C:\Qt\Tools\mingw530_32\bin
set LLVM_PATH=C:\Appli\LLVM\bin
set CMAKE_PATH=C:\Appli\CMake\bin
set NINJA_PATH=C:\Appli\Ninja

set PERL_SITE_PATH=C:\Perl64\site\bin
set PERL_PATH=C:\Perl64\bin
set PYTHON_PATH=C:\Appli\Python\Python36-32
set SCAN_BUILD_PATH=C:\Dev\CNRS-DEV\cfe\tools\scan-build\bin


set PATH=%QT_QMAKE_PATH%;%QT_MINGW_PATH%;%PERL_SITE_PATH%;%PERL_PATH%;%PYTHON_PATH%;%SCAN_BUILD_PATH%;%LLVM_PATH%;%CMAKE_PATH%;%NINJA_PATH%;%PATH%
cd /D C:\Dev\CNRS-DEV\SciQlopInit
