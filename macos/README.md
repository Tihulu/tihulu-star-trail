# macOS

This folder contains the macOS-specific installer and application bundle builder.

- `install.sh` installs Homebrew when needed, all dependencies, the isolated Python runtime, CLI launcher, and `.app` bundle.
- `build-app.sh` rebuilds the Finder-launchable `.app` bundle for an existing installation.
- `build-dmg.sh` creates a standalone PyInstaller application and release DMG.

End users can download Apple Silicon and Intel DMG files from the
[latest GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/latest).
Each DMG includes its matching FFmpeg binary, so no Homebrew, Python, or
separate FFmpeg installation is needed for MP4 or timelapse export.

From the repository root, run:

```sh
./macos/install.sh
```

The app is installed at `~/Applications/Tihulu Star Trail.app` by default.

To build a release DMG on macOS:

```sh
python3 -m pip install ".[release]"
./macos/build-dmg.sh
```

The DMG is written to `release-dist/`. GitHub Actions runs this builder on
separate Apple Silicon and Intel runners for tagged releases.
