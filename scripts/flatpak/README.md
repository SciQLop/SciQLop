# Flatpak packaging for SciQLop

## Build locally

```bash
# Install the KDE runtime and SDK (one-time)
flatpak install flathub org.kde.Platform//6.9 org.kde.Sdk//6.9

# Build and install
flatpak-builder --user --install --force-clean build \
    scripts/flatpak/com.github.SciQLop.SciQLop.yaml

# Run
flatpak run com.github.SciQLop.SciQLop
```

## Updating dependencies

After changing `pyproject.toml`, regenerate the pip dependency manifest:

```bash
# Requires: pip install flatpak-pip-generator
./scripts/flatpak/update-deps.sh
```

This updates `python-deps.yaml` (auto-generated, ~23 modules).

`pyside6-deps.yaml` must be updated **manually** when changing PySide6, shiboken6, or PySide6-QtAds versions — get the wheel URLs and sha256 hashes from PyPI.

## File layout

| File | Description |
|---|---|
| `com.github.SciQLop.SciQLop.yaml` | Main Flatpak manifest |
| `python-deps.yaml` | Auto-generated pip deps (via `update-deps.sh`) |
| `pyside6-deps.yaml` | PySide6/shiboken6/QtAds/SciQLopPlots x86_64 wheels (manual) |
| `update-deps.sh` | Regenerates `python-deps.yaml` |

## Sandbox permissions

| Permission | Reason |
|---|---|
| `--share=network` | Download data from AMDA/CDAWeb/SSCWeb, workspace pip installs |
| `--filesystem=home` | Read/write workspaces, CDF files, config |
| `--device=dri` | GPU-accelerated rendering |
| `--socket=wayland` + `fallback-x11` | Display |
| `--talk-name=org.freedesktop.secrets` | Keyring access for API tokens |

## Publishing to Flathub

Submit a PR to `github.com/flathub/com.github.SciQLop.SciQLop` with the manifest files. Flathub CI builds and publishes automatically.
