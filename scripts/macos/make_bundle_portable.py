import sys
import os
import subprocess
from typing import List
import shutil
import argparse
import re

parser = argparse.ArgumentParser(description='Fix libraries in a macOS bundle')
parser.add_argument('bundle', type=str, help='Path to the bundle')
args = parser.parse_args()

arch = os.uname().machine

if arch == 'x86_64':
    arch_to_remove = 'arm64'
else:
    arch_to_remove = 'x86_64'


def non_empty(x: str) -> bool:
    return len(x) > 0


def non_system(x: str) -> bool:
    return not x.startswith('/System/Library/Frameworks/') and not x.startswith('/usr/lib/')


_qt_or_sciqlop = re.compile('pyside|SciQLopPlots|shiboken|qt', flags=re.IGNORECASE)


def non_qt_or_sciqlop(x: str) -> bool:
    return not len(_qt_or_sciqlop.findall(x))


def is_library(x: str) -> bool:
    return x.split('.')[-1] in ('dylib', 'so')


def prepend_path(path: str, files: List[str]) -> List[str]:
    return list(map(lambda x: os.path.join(path, x), files))


def find_libraries(path: str) -> List[str]:
    libraries = []
    for root, _, files in os.walk(path):
        libraries += prepend_path(root, filter(non_qt_or_sciqlop, filter(is_library, files)))
    return libraries


def list_dependencies(library: str) -> List[str]:
    raw = subprocess.check_output(['otool', '-L', library]).decode('utf-8').split('\n')[1:]
    if len(raw):
        dependencies = list(filter(non_empty, map(lambda x: x.split(' ')[0].strip(), raw)))
        return dependencies
    return []


list_non_system_or_qt_dependencies = lambda x: list(filter(non_qt_or_sciqlop, filter(non_system, list_dependencies(x))))


def drop_unused_archs(library: str):
    subprocess.run(['lipo', '-remove', arch_to_remove, '-output', library, library])


def copy(src: str, dst: str):
    if not os.path.exists(dst):
        print(f'copying {src} to {dst}')
        shutil.copy(src, dst)


def install_name_tool_change(library: str, src_dependency: str):
    print(f'change {src_dependency} to @rpath/{os.path.basename(src_dependency)} in {os.path.basename(library)}')
    subprocess.run(
        ['install_name_tool', '-change', src_dependency, '@rpath/' + os.path.basename(src_dependency),
         library])


def in_directory(file, directory):
    # make both absolute
    directory = os.path.join(os.path.realpath(directory), '')
    file = os.path.realpath(file)

    # return true, if the common prefix of both is equal to directory
    # e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b
    return os.path.commonprefix([file, directory]) == directory


def relocate_dependency(library: str, src_dependency: str, bundle_lib_path: str):
    if not src_dependency.startswith("@") and os.path.exists(src_dependency):
        relocated_dependency = os.path.join(bundle_lib_path, os.path.basename(src_dependency))
        if not in_directory(src_dependency, bundle_lib_path):
            copy(src_dependency, relocated_dependency)
        else:
            relocated_dependency = src_dependency
        install_name_tool_change(library, src_dependency)
        if os.path.basename(src_dependency) != os.path.basename(relocated_dependency):
            fix_library(relocated_dependency, bundle_lib_path)


def fix_library(library: str, bundle_lib_path):
    print(f'Fixing {os.path.basename(library)}')
    dependencies = list_non_system_or_qt_dependencies(library)
    for src_dependency in dependencies:
        relocate_dependency(library, src_dependency, bundle_lib_path)


def is_macos_binary(file: str) -> bool:
    return subprocess.run(['file', file], stdout=subprocess.PIPE).stdout.decode('utf-8').find('Mach-O') != -1


def is_multiarch_macos_binary(file: str) -> bool:
    if not is_macos_binary(file):
        return False
    lipo_info = subprocess.run(['lipo', '-info', file], stdout=subprocess.PIPE).stdout.decode('utf-8')
    is_fat = lipo_info.find('Non-fat') == -1
    has_arch = lipo_info.find(arch_to_remove) != -1
    return is_fat and has_arch


def reduce_binaries(bundle: str):
    for root, _, files in os.walk(bundle):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                if os.access(file_path, os.X_OK):
                    if is_multiarch_macos_binary(file_path):
                        print(f'Reducing {file_path}')
                        drop_unused_archs(file_path)


def add_rpath_to_executable(executable: str, rpath: str):
    print(f'Adding rpath {rpath} to {executable}')
    subprocess.run(['install_name_tool', '-add_rpath', rpath, executable])


def main():
    bundle = args.bundle
    bundle_lib_path = os.path.join(bundle, 'Contents', 'Resources', 'usr', 'local', 'lib')
    bundle_bin_path = os.path.join(bundle, 'Contents', 'Resources', 'usr', 'local', 'bin')
    os.makedirs(bundle_lib_path, exist_ok=True)
    libraries = find_libraries(bundle)
    for library in libraries:
        print(f'Fixing {library}')
        fix_library(library, bundle_lib_path)
    for file in os.listdir(bundle_bin_path):
        if is_macos_binary(file):
            add_rpath_to_executable(file, '@executable_path/../lib')
    reduce_binaries(bundle)


if __name__ == '__main__':
    main()
