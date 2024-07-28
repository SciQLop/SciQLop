import os

arch = os.uname().machine

template = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
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
    <key>CFBundleVersion</key>
        <string>0.6</string>
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
    print(template.format(arch=arch))


if __name__ == '__main__':
    main()
