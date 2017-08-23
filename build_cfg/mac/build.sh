#!/bin/bash

mkdir build
meson --prefix=/tmp/SciQLOP.app --bindir=Contents/MacOS build
cd build
ninja
ninja install

