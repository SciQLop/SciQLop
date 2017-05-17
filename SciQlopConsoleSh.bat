@echo off
set GIT_HOME=C:\Users\mperrinel\AppData\Local\Atlassian\SourceTree\git_local
set SCIQLOP_SOURCE_PATH=C:\Dev\CNRS-DEV\SciQlopInit

set QT_QMAKE_PATH=C:\Qt\5.8\mingw53_32\bin
set QT_MINGW_PATH=C:\Qt\Tools\mingw530_32\bin
set LLVM_PATH=C:\Appli\LLVM\bin
set CMAKE_PATH=C:\Appli\CMake\bin
set NINJA_PATH=C:\Appli\Ninja

set PERL_SITE_PATH=C:\Perl64\site\bin
set PERL_PATH=C:\Perl64\bin
set PYTHON_PATH=C:\Appli\Python\Python36-32
set SCAN_BUILD_PATH=C:\Dev\CNRS-DEV\cfe\tools\scan-build\bin

:: Qt5 et Mingw 5.3.0
set PATH=%QT_QMAKE_PATH%;%QT_MINGW_PATH%;%PERL_SITE_PATH%;%PERL_PATH%;%PYTHON_PATH%;%SCAN_BUILD_PATH%;%LLVM_PATH%;%CMAKE_PATH%;%NINJA_PATH%;%PATH%


:: Ouverture de git-bash
echo Lancement de git bash
start %GIT_HOME%\git-bash.exe --cd=%SCIQLOP_SOURCE_PATH%