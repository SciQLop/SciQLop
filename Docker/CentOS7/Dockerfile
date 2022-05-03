FROM centos:7

RUN  yum update -y && \
     yum install -y epel-release wget zlib-devel && \
     yum install -y /usr/bin/7z meson /usr/include/uuid/uuid.h /usr/include/GL/gl.h centos-release-scl fontconfig libX11 pulseaudio-libs-glib2 && \
     yum install -y devtoolset-9 && \
     yum -y install https://packages.endpoint.com/rhel/7/os/x86_64/endpoint-repo-1.7-1.x86_64.rpm && \
     yum install -y git cmake3 python3-devel python3-setuptools python3-wheel && \
     cd /tmp && \
     wget --quiet  http://ftp2.nluug.nl/languages/qt/development_releases/prebuilt/libclang/libclang-release_60-linux-Rhel7.2-gcc5.3-x86_64-clazy.7z && \
     7z x libclang-release_60-linux-Rhel7.2-gcc5.3-x86_64-clazy.7z && \
     mv libclang /opt/libclang_60 && \
     CFLAGS="-std=gnu99" pip3 install --user cuteci numpy spwc qtconsole pyinstaller && \
     $HOME/.local/bin/cuteci --rm --installer http://download.qt.io/official_releases/qt/5.12/5.12.2/qt-opensource-linux-x64-5.12.2.run install --destdir $HOME/Qt --packages qt.qt5.5122.gcc_64 && \
     mkdir $HOME/SciQLOP_build && \
     cd $HOME/SciQLOP_build && \
     git clone https://code.qt.io/pyside/pyside-setup && \
     cd pyside-setup && \
     git checkout 5.12.6 && \
     source /opt/rh/devtoolset-9/enable && \
     export LLVM_INSTALL_DIR=/opt/libclang_60 && \
     python3 setup.py install --qmake=$HOME/Qt/5.12.2/gcc_64/bin/qmake --parallel=8  --cmake=/usr/bin/cmake3 --user && \
     cd $HOME/SciQLOP_build && \
     git clone --recursive --branch=PySide2 https://github.com/SciQLop/SciQLop && \
     cd SciQLop && \
     LIBRARY_PATH=/opt/libclang_60/lib/ LD_LIBRARY_PATH=/opt/libclang_60/lib/ PATH=$HOME/Qt/5.12.2/gcc_64/bin/:$HOME/.local/bin:$PATH meson . build && \
     cd build && \
     LIBRARY_PATH=/opt/libclang_60/lib/ LD_LIBRARY_PATH=/opt/libclang_60/lib/ ninja -j 4 && \
     echo 'LD_LIBRARY_PATH=/opt/libclang_60/lib/:$HOME/Qt/5.12.2/gcc_64/lib/ python3 main.py' > $HOME/SciQLOP_build/SciQLop/build/app/PySide2-bindings/start.sh && \
     cd $HOME/SciQLOP_build/SciQLop/build/app/PySide2-bindings/ && \
     $HOME/.local/bin/pyinstaller --name="SciQLop" --windowed  --hidden-import=spwc --hidden-import=numpy --add-data=$HOME/Qt/5.12.2/gcc_64/plugins/platforms:platforms --add-data=plugins:plugins main.py 


