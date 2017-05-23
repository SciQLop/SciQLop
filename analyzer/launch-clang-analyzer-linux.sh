
QT_PATH=".../Qt/5.8/gcc_64/lib/cmake/"

export CC=/usr/libexec/ccc-analyzer
export CXX=/usr/libexec/c++-analyzer
export CCC_CC=clang
export CCC_CXX=clang++
export LD=clang++
export CCC_ANALYZER_VERBOSE=1

LD_LIBRARY_PATH=/usr/local/lib64
export LD_LIBRARY_PATH

rm -rf build_clang-analyzer
mkdir build_clang-analyzer
cd build_clang-analyzer

scan-build cmake -DCMAKE_PREFIX_PATH=$QT_PATH -DCMAKE_CXX_COMPILER=clazy -DENABLE_ANALYSIS=false -DENABLE_CPPCHECK=false -DENABLE_FORMATTING=false -DENABLE_CHECKSTYLE=false -BUILD_DOCUMENTATION=false -BUILD_TESTS=false -DCMAKE_BUILD_TYPE=Debug ../../SCIQLOP-Initialisation/

scan-build -o clang-analyzer-output make -j2
