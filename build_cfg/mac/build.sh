#!/bin/bash
# On OS X only 0.49.1 works :(
pip3 install --upgrade --user meson==0.49.1
HERE=$( cd "$(dirname "$0")" ; pwd -P )
mkdir build
~/Library/Python/3.7/bin/meson -Dcpp_args='-DQT_STATICPLUGIN' -Ddefault_library=static --prefix=/tmp/SciQLOP.app --bindir=Contents/MacOS build
cd build
ninja
ninja install
~/Library/Python/3.7/bin/virtualenv --always-copy /tmp/SciQLOP.app
~/Library/Python/3.7/bin/virtualenv --relocatable /tmp/SciQLOP.app
source /tmp/SciQLOP.app/bin/activate
/tmp/SciQLOP.app/bin/pip install speasy
cp $HERE/SciQLOP_wrapper /tmp/SciQLOP.app/Contents/MacOS/
chmod +x /tmp/SciQLOP.app/Contents/MacOS/SciQLOP_wrapper
