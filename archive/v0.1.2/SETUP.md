# Setup guide: archived v0.1.2 desktop apps

Use this guide when you specifically need the desktop release that predates
the manual thumbnail grid and photo drag-and-drop workspace. It is preserved
separately so later installers do not replace it by accident.

## macOS

Run the archived setup script from the repository root:

```sh
./archive/v0.1.2/setup-macos-dmg.sh
```

It detects Apple Silicon (`arm64`) or Intel (`x86_64`), downloads the matching
DMG, and opens it. Drag **Tihulu Star Trail** to Applications. The DMG contains
Python, RAW support, and FFmpeg, so MP4 and timelapse export needs no Homebrew,
Python, or FFmpeg installation. The release is ad-hoc signed, not notarized;
on first opening, Control-click the app and choose **Open** if macOS asks.

## Debian, Ubuntu, and Pop!_OS

Run:

```sh
./archive/v0.1.2/setup-linux-appimage.sh
```

This installs the x86_64 AppImage and its no-FUSE launcher under
`~/Applications/Tihulu-Star-Trail-v0.1.2` by default. Run the AppImage
directly. If the system does not have `libfuse2`, run the adjacent
`-no-fuse.sh` launcher instead. The AppImage includes Python, RAW support, and
FFmpeg for MP4 and timelapse export.

## Verify downloads

Compare your downloaded files against
[v0.1.2 SHA256SUMS.txt](https://github.com/Tihulu/tihulu-star-trail/releases/download/v0.1.2/SHA256SUMS.txt).
All archived release assets are listed on the
[v0.1.2 release page](https://github.com/Tihulu/tihulu-star-trail/releases/tag/v0.1.2).
