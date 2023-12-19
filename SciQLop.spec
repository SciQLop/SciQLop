# -*- mode: python ; coding: utf-8 -*-
from sys import platform
import os
import sys
import argparse
import jupyterlab
import qtconsole
from importlib.metadata import requires, metadata
import importlib_metadata
import pkg_resources
import re
import pandocfilters
import SciQLop

def top_packages(package):
    try:
        fname = f"{pkg_resources.get_distribution(package).egg_info}/RECORD"
        return list(set(filter(lambda l: ".py," not in l, map(lambda l:l.split('/')[0], filter(lambda l:".py," in l, open(fname).readlines())))))
    except:
        return [package]


def is_base_dep(dep):
    return len(dep.split(";")) == 1


def get_base_dependencies(package):
    p_re = p_re = re.compile("([\w\d\-_]+)([>=<]*).*")
    if package is None:
        return []
    try:
        requirements = requires(package)
    except:
        return []
    if requirements is None:
        return []
    return list(map(lambda p: p_re.match(p).groups()[0], filter(is_base_dep, requirements)))

def get_all_dependencies(*packages):
    def _get_all_dependencies(package, _known_deps=None):
        if package is None:
            return []
        base_deps = set(get_base_dependencies(package))
        if _known_deps is None:
            _known_deps = set()
        new_deps = [_get_all_dependencies(dep, _known_deps.union(base_deps)) for dep in base_deps.difference(_known_deps)]
        new_deps = [dep for subdep in new_deps for dep in subdep]
        return list(base_deps.union(new_deps))
    dependencies = list(set([dep for package in packages for dep in _get_all_dependencies(package)]))
    dependencies = list(map(top_packages, dependencies))
    return [dep for subdep in dependencies for dep in subdep ]




parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
options = parser.parse_args()


from PyInstaller.utils.hooks import collect_all, copy_metadata
block_cipher = None

icon = None

datas = [('SciQLop/resources/*','SciQLop/resources'),('SciQLop/plugins/*','SciQLop/plugins')]
binaries = [(sys.executable, '.')]
if os.path.exists('/lib/x86_64-linux-gnu/libcrypt.so.1'):
    binaries.append( ('/lib/x86_64-linux-gnu/libcrypt.so.1', '.') )

hiddenimports = ['markupsafe', 'tscat_gui', 'SciQLop', 'SciQLop.widgets.plots.time_span', 'SciQLop.widgets.plots.time_span_controller', 'SciQLop.plugins.catalogs.lightweight_manager', 'SciQLop.backend.pipelines_model.easy_provider']

distributions = importlib_metadata.packages_distributions()

def add_all_from_module(name):
    global datas, binaries, hiddenimports
    tmp_ret = collect_all(name)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    paths = distributions.get(name)
    if paths is not None:
        for path in paths:
            datas += copy_metadata(path)

list(map(add_all_from_module, get_all_dependencies("SciQLop", "jupyterlab", "jupyterlab_widgets", "jupyterlab_pygments", "jupyterlab_server", "qtconsole", "pandocfilters")))

add_all_from_module("jupyterlab")
add_all_from_module("jupyterlab_server")
add_all_from_module("jupyterlab_server.extension")
add_all_from_module("SciQLop.Jupyter")
add_all_from_module("SciQLop")
add_all_from_module("pandocfilters")
add_all_from_module("jupyterlab_widgets")
add_all_from_module("qtconsole")
add_all_from_module("jupyter_server/extension")
add_all_from_module("notebook_shim")

datas += [ (f"{sys.prefix}/share/jupyter", 'share/jupyter'), (f"{sys.prefix}/etc/jupyter", 'etc/jupyter'), (pandocfilters.__file__, os.path.basename(pandocfilters.__file__))]

if not os.path.exists(f"{pkg_resources.get_distribution('SciQLop').egg_info}/RECORD"):
    datas += [('SciQLop/Jupyter/entry_points.txt', f"SciQLop-{SciQLop.__version__}.dist-info/entry_points.txt")]

if platform.startswith("darwin"):
    icon = 'SciQLop/resources/icons/SciQLop.png'

sciqlop_files = ['SciQLop/app.py', 'SciQLop/widgets/__init__.py', 'SciQLop/plugins/speasy.py', 'SciQLop/plugins/test_plugin.py', 'SciQLop/plugins/catalogs/__init__.py', 'SciQLop/plugins/catalogs/lightweight_manager/__init__.py']

a = Analysis(sciqlop_files,
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

