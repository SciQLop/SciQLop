#!/bin/bash

mkdir build
meson --prefix=/tmp/SciQLOP --cross-file build_cfg/windows/cross_fedora_win64.txt build
cd build
ninja
ninja install

