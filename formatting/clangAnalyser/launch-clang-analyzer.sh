#!/usr/bin/bash

function usage {
    echo "  usage: $0 [ninja|make]"
    echo "    Launch clang-analyzer on the sources with ninja or make."
    exit
}

function execAndTest {
    "$@"
    local status=$?
    if [ $status -ne 0 ]; then
        echo "" >&2
        echo "  ERROR with $1" >&2
        exit $status
    fi
    return $status
}

# Défaut : Ninja
generator="Ninja"
builder="ninja"

if [[ $# -gt 1 ]]; then
    echo "  ERROR: illegal number of arguments." >&2
    echo "    provided: $#" >&2
    echo "    expected: 0 or 1" >&2
    echo "" >&2
    usage
elif [[ $# -eq 1 ]]; then
    if [[ "$1" == "ninja" ]]; then
        echo "=> Using multiple jobs"
        generator="Ninja"
        builder="ninja"
    elif [[ "$1" == "make" ]]; then
        echo "=> Using single job"
        generator="Ninja"
        builder="ninja -j 1"
    elif [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        usage
    else
        echo "  ERREUR:" >&2
        echo "    L'option doit être 'ninja' ou 'make'" >&2
        echo "" >&2
        exit -1
    fi
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# On se place à la racine du projet SciQlop
execAndTest cd $DIR
if ! [ -e CMakeLists.txt -a -e README.md ]; then
    echo "  ERREUR:" >&2
    echo "    CMakeLists.txt ou README.md n'existent pas." >&2
    echo "    Verifier que le script est bien execute a partir" >&2
    echo "    du sous-dossier 'scripts' de SciQlop" >&2
    echo ""
    exit 1
fi

# Vérification de l'existence de scan-build, ccc-analyzer, ccc-analyzer.bat
# et c++-analyzer.bat
export SCAN_BUILD_DIR="C:/Dev/CNRS-DEV/cfe/tools/scan-build"
export CLANG_BUILD_DIR="C:/Appli/LLVM/bin"
if ! [ -e $SCAN_BUILD_DIR/bin/scan-build \
        -a -e $SCAN_BUILD_DIR/libexec/ccc-analyzer \
        -a -e $SCAN_BUILD_DIR/libexec/ccc-analyzer.bat \
        -a -e $SCAN_BUILD_DIR/libexec/c++-analyzer.bat ]; then
    echo "  ERREUR:"
    echo "    Les fichiers scan-build, ccc-analyzer, ccc-analyzer.bat"
    echo "    et c++-analyzer.bat ne sont pas présents dans le dossier :"
    echo "    $SCAN_BUILD_DIR."
    echo "    Assurez-vous d'avoir installé clang-analyzer en relançant le"
    echo "    script d'installation d'environnement de SciQlop."
    echo ""
    exit 2
fi

# Création d'un dossier build/debug_clanganalyzer et cd dedans
execAndTest mkdir -p build/debug_clanganalyzer
execAndTest cd build/debug_clanganalyzer

# Création d'un dossier clang-analyzer-output pour recevoir les
# rapports
execAndTest mkdir -p clang-analyzer-output

# Export des compilateurs pour clang-analyzer
export CCC_CC=gcc
export CCC_CXX=g++

# Exécution de cmake avec scan-build pour initialiser clang-analyzer
execAndTest $SCAN_BUILD_DIR/bin/scan-build \
        -o clang-analyzer-output \
        --use-analyzer $CLANG_BUILD_DIR/clang.exe \
    cmake -G "$generator" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_COMPILER=C:/Appli/LLVM/libexec/c++-analyzer.bat \
        -DCMAKE_C_COMPILER=C:/Appli/LLVM/libexec/ccc-analyzer.bat \
		-DCMAKE_CXX_COMPILER_ID=GNU \
        -DBUILD_TESTS=NONE \
        -DENABLE_CHECKSTYLE=OFF \
        -DENABLE_CODE_ANALYSIS=OFF \
        -DENABLE_FORMATTING=OFF \
        ../..

# Clean de la construction pour avoir tous les bugs tout le temps
execAndTest $builder clean

# Exécution de ninja avec scan-build pour lancer clang-analyzer
execAndTest $SCAN_BUILD_DIR/scan-build \
        -o clang-analyzer-output \
        --use-analyzer $CLANG_BUILD_DIR/clang.exe \
    $builder
