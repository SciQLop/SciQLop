#!/bin/env python3

import os
import sys
import argparse
from jinja2 import Template


parser = argparse.ArgumentParser(description='SciQLop main generator')
parser.add_argument('--input')
parser.add_argument('--qt_version')
parser.add_argument('--output')
args = parser.parse_args()

if args.qt_version == 'qt6':
    pyside_ver = '6'
else:
    pyside_ver = '2'

with open(args.input,'r') as input:
    j2_template = Template(input.read())
    with open(args.output,'w') as output:
        output.write(j2_template.render(
        {
            'pyside_package': f'PySide{pyside_ver}'
        }
        ))

