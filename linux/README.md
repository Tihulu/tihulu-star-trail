# Linux AppImage

GitHub Releases provide a self-contained x86_64 AppImage for Debian 12,
Ubuntu 22.04, Pop!_OS 22.04, and newer compatible distributions. It includes
an x86_64 FFmpeg binary for MP4 and timelapse export.

Download the AppImage, make it executable, and run it:

```sh
chmod +x Tihulu-Star-Trail-*-linux-x86_64.AppImage
./Tihulu-Star-Trail-*-linux-x86_64.AppImage
```

To build the AppImage on Linux, install the project and PyInstaller, then run:

```sh
python3 -m pip install ".[release]"
./linux/build-appimage.sh
```

The build script downloads the official `appimagetool` executable when
`APPIMAGETOOL` is not provided. Output is written to `release-dist/`.
