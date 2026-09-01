#!/usr/bin/env sh
set -e

SCRIPT_DIR=$(dirname "$0")
ABSOLUTE_SCRIPT_DIR=$(readlink -f "$SCRIPT_DIR")
SCIQLOP_ROOT=$ABSOLUTE_SCRIPT_DIR/../../

PYTHON_VERSION=3.14
NODE_VERSION=24.17.0
UV_VERSION=0.11.21
UV_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"

WORK=/tmp/sciqlop
APPDIR=$WORK/SciQLop.AppDir

mkdir -p $WORK
cd $WORK

########################################
# Clean previous build
########################################

rm -rf $APPDIR
mkdir -p $APPDIR/opt/uv
mkdir -p $APPDIR/usr/local

########################################
# Fetch uv standalone
########################################

if [ ! -f uv.tar.gz ]; then
    wget -O uv.tar.gz "$UV_URL"
fi

tar -xzf uv.tar.gz
cp uv-*/uv $APPDIR/opt/uv/
chmod +x $APPDIR/opt/uv/uv

UV_BIN=$APPDIR/opt/uv/uv

########################################
# Fetch Python (python-build-standalone via uv)
########################################

$UV_BIN python install $PYTHON_VERSION --install-dir $APPDIR/opt

# uv creates $APPDIR/opt/cpython-<version+arch>/ — use it as-is.
# Do NOT rename: uv pip install recreates an absolute "python" symlink that
# breaks inside the AppImage at runtime.
PYTHON_DIR=$(ls -d $APPDIR/opt/cpython-* | head -1)
PYTHON_BIN=$PYTHON_DIR/bin/python$PYTHON_VERSION

# Ensure python3 symlink exists (not all python-build-standalone builds create it)
ln -sf python$PYTHON_VERSION $PYTHON_DIR/bin/python3

# Remove PEP 668 marker so uv pip install works
rm -f $PYTHON_DIR/lib/python${PYTHON_VERSION}/EXTERNALLY-MANAGED

########################################
# Install SciQLop (launcher only)
########################################

# The bare package is only the launcher — read the manifest/settings, then
# drive uv. It never imports the GUI stack (test_launcher_thin_imports.py),
# so it doesn't need [all] here: the application is installed into each
# workspace's own venv at first launch by prepare_workspace(), which also
# resolves plugin python_dependencies (SciQLop/plugins/*/plugin.json) into
# that same venv. Installing [all] or plugin deps into this bundled Python
# would bake the whole app into the AppImage, defeating the point of the
# self-contained-workspace split.
$UV_BIN pip install \
    --python $PYTHON_BIN \
    --reinstall \
    --no-cache \
    "$SCIQLOP_ROOT"

########################################
# SSL certificates (for distros without /etc/ssl/cert.pem)
########################################

$UV_BIN pip install --python $PYTHON_BIN certifi

########################################
# Bundle native launcher (splash while the bundled Python above prepares the
# workspace and starts the app — see launcher/src/launcher.cpp)
########################################

mkdir -p $APPDIR/opt/launcher
"$SCIQLOP_ROOT/scripts/fetch_launcher.sh" linux_x86_64 "$APPDIR/opt/launcher/sciqlop-launcher"
# splash.png beside the binary is optional (ui_fltk.cpp checks is_regular_file
# before loading it) — none shipped yet, the splash just shows text for now.

# Remove symlinks uv creates in opt/ (absolute, break inside AppImage mount)
# - "python" → cpython-<version>
# - "cpython-3.14-<arch>" → cpython-3.14.3-<arch> (minor-only alias)
find "$APPDIR/opt" -maxdepth 1 -type l -delete

########################################
# AppRun, desktop file, icon
########################################

APP_RUN_SRC="$ABSOLUTE_SCRIPT_DIR/AppRun"
APP_RUN_DST="$APPDIR/AppRun"

if [ -n "$SCIQLOP_DEBUG" ]; then
    sed '/^#export SCIQLOP_DEBUG="1"/s/^#//' "$APP_RUN_SRC" > "$APP_RUN_DST"
else
    cp "$APP_RUN_SRC" "$APP_RUN_DST"
fi
chmod +x "$APP_RUN_DST"

cp $SCIQLOP_ROOT/SciQLop/resources/icons/SciQLop.png $APPDIR/sciqlop.png

cat > $APPDIR/sciqlop.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=SciQLop
Icon=sciqlop
Exec=SciQLop
Categories=Science;
EOF

########################################
# Bundle NodeJS
########################################

if [ ! -f node-v$NODE_VERSION-linux-x64.tar.xz ]; then
    curl -LO https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.xz
fi
tar -xJf node-v$NODE_VERSION-linux-x64.tar.xz -C $WORK
rsync -avhu $WORK/node-v$NODE_VERSION-linux-x64/* $APPDIR/usr/local/

########################################
# Build final AppImage
########################################

if [ ! -f ./appimagetool-x86_64.AppImage ]; then
    wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

./appimagetool-x86_64.AppImage --appimage-extract-and-run -n $APPDIR SciQLop-x86_64.AppImage

mkdir -p $SCIQLOP_ROOT/dist
mv SciQLop-x86_64.AppImage* $SCIQLOP_ROOT/dist/

cd -
