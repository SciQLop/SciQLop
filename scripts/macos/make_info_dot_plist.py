import os
import re
import sys


def _read_version() -> str:
    """Return SciQLop's marketing version (major.minor.patch) from pyproject.toml.

    PEP 440 dev/pre-release suffixes are stripped so the value is a valid
    macOS CFBundleShortVersionString (three period-separated integers).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    pyproject = os.path.join(here, "..", "..", "pyproject.toml")
    with open(pyproject, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^version\s*=\s*"([^"]+)"', line)
            if m:
                raw = m.group(1)
                match = re.match(r"^(\d+)\.(\d+)\.(\d+)", raw)
                if not match:
                    print(f"Cannot derive bundle version from '{raw}'", file=sys.stderr)
                    sys.exit(1)
                return f"{match[1]}.{match[2]}.{match[3]}"
    print("No 'version = ...' line found in pyproject.toml", file=sys.stderr)
    sys.exit(1)


arch = os.uname().machine
version = _read_version()

template = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundlePackageType</key>
        <string>APPL</string>
    <key>CFBundleExecutable</key>
        <string>SciQLop</string>
    <key>LSArchitecturePriority</key>
        <array>
            <string>{arch}</string>
        </array>
    <key>LSRequiresNativeExecution</key>
        <true/>
    <key>CFBundleIdentifier</key>
        <string>com.LPP.SciQLop</string>
    <key>CFBundleName</key>
        <string>SciQLop</string>
    <key>CFBundleShortVersionString</key>
        <string>{version}</string>
    <key>CFBundleVersion</key>
        <string>{version}</string>
    <key>CFBundleIconFile</key>
        <string>SciQLop.icns</string>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
        <true/>
    <key>NSHighResolutionCapable</key>
        <true/>
</dict>
</plist>
'''


def main():
    print(template)


if __name__ == '__main__':
    main()
