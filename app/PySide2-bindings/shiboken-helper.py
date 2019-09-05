#!/bin/env python3

import os
import sys
import importlib
import argparse
from glob import glob


shiboken2_generator = importlib.import_module('shiboken2_generator')
shiboken2 = importlib.import_module('shiboken2')
PySide2 = importlib.import_module('PySide2')


parser = argparse.ArgumentParser(description='PySide2/shiboken2 ')
group = parser.add_mutually_exclusive_group()
group.add_argument('--libs',action='store_true')
group.add_argument('--includes',action='store_true')
parser.add_argument('--modules')
group.add_argument('--typesystem', action='store_true')
args = parser.parse_args()


def first_existing_path(path_list):
    return next((path for path in path_list if os.path.exists(path)), None)


if shiboken2.__file__ and shiboken2_generator.__file__ and PySide2.__file__:
    PySide2_inc = first_existing_path([PySide2.__path__[0]+'/include','/usr/include/PySide2'])
    PySide2_typesys = first_existing_path([PySide2.__path__[0]+'/typesystems','/usr/share/PySide2/typesystems'])
    PySide2_includes = first_existing_path([PySide2.__path__[0]+'/include','/usr/include/PySide2'])
    shiboken2_includes = first_existing_path([shiboken2.__path__[0]+'/include','/usr/include/shiboken2'])
    
    if args.typesystem:
        print(PySide2_typesys)
    modules = args.modules.split(',')
    if args.libs:
        main_lib = (glob(shiboken2.__path__[0]+'/libshiboken2'+importlib.machinery.EXTENSION_SUFFIXES[0])+glob("/usr/lib64/"+'/libshiboken2'+importlib.machinery.EXTENSION_SUFFIXES[0]))[0]
        main_lib += " "+(glob(PySide2.__path__[0]+'/libpyside2'+importlib.machinery.EXTENSION_SUFFIXES[0])+glob("/usr/lib64/"+'/libpyside2'+importlib.machinery.EXTENSION_SUFFIXES[0]))[0]
        modules_libs = [importlib.import_module(f'PySide2.{module}').__file__ for module in modules]
        print(" ".join([main_lib]+ modules_libs))
    if args.includes:
        modules_incs = [f"-I{PySide2_includes}/{module}" for module in modules]
        print(" ".join([f"-I{PySide2_includes} -I{shiboken2_includes}"]+ modules_incs))
    
    
