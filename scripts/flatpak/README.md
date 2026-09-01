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

`python-deps.yaml` only covers the **launcher's** own small dependency
closure (platformdirs, pydantic, pyyaml, tomli_w) — the application itself
(PySide6, shiboken6, QtAds, SciQLopPlots, matplotlib, speasy, ...) is not
bundled into `/app` at all. It's installed into a per-user workspace venv
at first launch by `prepare_workspace()`, the same as the AppImage/macOS/
Windows installers — see `pip install sciqlop` vs `sciqlop[all]` in the
root `pyproject.toml`.

After changing the bare `dependencies` list in `pyproject.toml`, regenerate:

```bash
# Requires: pip (for downloading wheels), PyYAML
./scripts/flatpak/update-deps.sh
```

This updates `python-deps.yaml` (auto-generated, currently ~8 modules).

## File layout

| File | Description |
|---|---|
| `com.github.SciQLop.SciQLop.yaml` | Main Flatpak manifest |
| `python-deps.yaml` | Auto-generated launcher deps (via `update-deps.sh`) |
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
