#!/bin/bash

mkdir build
meson -Dcpp_args='-DQT_STATICPLUGIN' -Ddefault_library=static --prefix=/tmp/SciQLOP.app --bindir=Contents/MacOS build
cd build
ninja
ninja install

