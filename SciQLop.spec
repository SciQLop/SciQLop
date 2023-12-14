# -*- mode: python ; coding: utf-8 -*-
from sys import platform
import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
options = parser.parse_args()

from PyInstaller.utils.hooks import collect_all
block_cipher = None

icon = None

datas = [('SciQLop/resources/*','SciQLop/resources'),('SciQLop/plugins/*','SciQLop/plugins')]
binaries = []
if os.path.exists('/lib/x86_64-linux-gnu/libcrypt.so.1'):
    binaries.append( ('/lib/x86_64-linux-gnu/libcrypt.so.1', '.') )

hiddenimports = ['tscat_gui', 'SciQLop', 'SciQLop.widgets.plots.time_span', 'SciQLop.widgets.plots.time_span_controller', 'SciQLop.plugins.catalogs.lightweight_manager', 'SciQLop.backend.pipelines_model.easy_provider']

def add_all_from_module(name):
    global datas, binaries, hiddenimports
    tmp_ret = collect_all(name)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

add_all_from_module('astroquery')
add_all_from_module('debugpy')
add_all_from_module('speasy')
add_all_from_module('pycdfpp')
add_all_from_module('pyistp')
add_all_from_module('qtconsole')
add_all_from_module('jupyterlab')


if platform.startswith("darwin"):
    icon = 'SciQLop/resources/icons/SciQLop.png'

a = Analysis(['SciQLop/app.py', 'SciQLop/widgets/__init__.py', 'SciQLop/plugins/speasy.py', 'SciQLop/plugins/test_plugin.py', 'SciQLop/plugins/catalogs/__init__.py', 'SciQLop/plugins/catalogs/lightweight_manager/__init__.py'],
             binaries=binaries,
             datas=datas,
             hookspath=[],
             runtime_hooks=[],
             excludes=['PySide6.QtQuick', 'libQt6Quick.so.6', 'libstdc++.so.6'],
             hiddenimports=hiddenimports,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)


pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)


if platform.startswith("darwin"):
    exe = EXE(pyz,
              a.scripts,
              [],
              exclude_binaries=True,
              name='SciQLop',
              debug=True,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              upx_exclude=[],
              icon=icon,
              runtime_tmpdir=None,
              console=False )

    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   strip=False,
                   upx=True,
                   name='SciQLop')

    app = BUNDLE(coll,
      name='SciQLop.app',
      icon=icon,
      bundle_identifier=None,
      info_plist={
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True
      })

else:
    exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='SciQLop',
          debug=options.debug,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False,
          icon="SciQLop/resources/icons/SciQLop.ico")

