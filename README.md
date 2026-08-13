# Tihulu Star Trail

**Hosted Web App:** https://tihulu.github.io/tihulu-star-trail/

**Native Downloads:** https://github.com/Tihulu/tihulu-star-trail/releases/latest

**OS Installation Guide:** [docs/INSTALLATION.md](docs/INSTALLATION.md)

Tihulu Star Trail is an open source native desktop and command-line application for macOS and Debian-based Linux systems, including Pop!_OS. It scans a folder or SD card, groups photos that look like they were taken from the same camera angle, and creates a star trail image for each group.

The grouping step uses OpenCV feature matching and a RANSAC homography check. In plain English: it looks for visual points that agree with each other geometrically, then groups images by how likely they are to share the same viewpoint.

## Features

- Recursively scans an SD card or photo folder.
- Opens a native Debian/Pop!_OS desktop app with `tihulu desktop`.
- Opens the same native feature set as a macOS `.app`, including RAW processing, manual group review, previews, and timelapse playback.
- Gives the native desktop app a manual group review workspace with multi-select photo moves/removal, group creation/renaming/reordering, 50-step undo, RAW-capable previews, and edited-group export.
- Previews completed trail images and plays completed timelapses inside the native desktop app.
- Lets native desktop users choose JPEG/PNG, MP4/WebM, output dimensions, original-size image export, video bitrate, and custom single-output names.
- Keeps the local browser interface available with `tihulu ui`.
- Includes a static GitHub Pages web app for browser-readable photo sets.
- Groups images by likely camera angle.
- Optionally uses EXIF capture time or file modified time to keep different sessions apart.
- Ignores hidden dot files such as `.DS_Store` or `._IMG_0001.JPG`.
- Lets the hosted web app browse every photo inside a group, multi-select thumbnails, drag selected photos between groups, drag group cards to reorder groups, drop photos into a new group, use arrow-key navigation, rename groups, add groups, undo manual edits, move photos between groups, create a new group, or remove photos from the working set.
- Provides a built-in parameter guide for threshold, preview size, export size, image/video formats and quality, FPS, and time metadata windows.
- Opens completed hosted-web timelapse exports in an in-page video player with native replay and seek controls.
- Lets hosted-web users type a custom download filename before saving trail images or timelapse videos.
- Converts Firefox-hosted WebM timelapse recordings to MP4 through FFmpeg WASM when MP4 is selected.
- Writes a JSON manifest with group scores and source paths.
- Creates star trails with a lighten blend, which is the classic pixel-wise maximum stack.
- Renders MP4 timelapse videos from full folders or detected groups.
- Supports JPEG, PNG, TIFF, WebP, and common RAW formats through `rawpy`.
- Keeps the original photos untouched.
- Can organize groups as symlinks, copies, hardlinks, or manifest-only output.

## Install On macOS

For requirements, install locations, verification, and troubleshooting, see the [complete macOS installation documentation](docs/INSTALLATION.md#macos).

Download the DMG for your Mac from the [latest GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/latest):

- Apple Silicon (`M1`, `M2`, `M3`, `M4`, or newer): download the `arm64.dmg` file.
- Intel Mac: download the `x86_64.dmg` file.

Open the DMG and drag **Tihulu Star Trail** into the Applications shortcut. Release builds are ad-hoc signed but not Apple-notarized, so the first launch may require Control-clicking the app and choosing **Open**.

The command-line installer remains available when you prefer a managed installation. The same one-line command installs Homebrew when it is missing, then installs Python 3.12, Tk, FFmpeg, Git when needed, and every Python dependency:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/macos/install.sh | sh
```

The installer uses the official Homebrew installer when necessary, installs Homebrew `python@3.12`, `python-tk@3.12`, and `ffmpeg`, creates an isolated runtime under `~/Library/Application Support/Tihulu Star Trail`, installs the CLI at `~/.local/bin/tihulu`, and builds a normal macOS application bundle. No Terminal window is shown when the app is launched from Applications, and the installed app keeps working if the original cloned repository is moved or deleted.

From a cloned repository, install or refresh the macOS app with:

```bash
./macos/install.sh
```

You can rebuild only the `.app` bundle after an existing installation with:

```bash
./macos/build-app.sh
```

The default install is user-local and does not require `sudo`. Set `TIHULU_APP_DIR=/Applications` if you intentionally want a system-wide application location and have permission to write there.

## Install On Debian Or Pop!_OS

For requirements, install locations, verification, and troubleshooting, see the [complete Debian/Pop!_OS installation documentation](docs/INSTALLATION.md#debian-and-pop_os).

Download the `linux-x86_64.AppImage` file from the [latest GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/latest), make it executable, and run it:

```bash
chmod +x Tihulu-Star-Trail-*-linux-x86_64.AppImage
./Tihulu-Star-Trail-*-linux-x86_64.AppImage
```

The AppImage is self-contained and targets x86_64 Debian 12, Ubuntu 22.04, Pop!_OS 22.04, and newer compatible distributions. Use the installer below when you want a managed virtual environment, command-line launcher, and application-menu entry.

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/scripts/install-debian.sh | sh
```

The installer adds a launcher at `~/.local/bin/tihulu` and a Pop!_OS/GNOME application entry named **Tihulu Star Trail**. That launcher opens the native Linux desktop app. If `~/.local/bin` is not already on your `PATH`, run the command with the full path or add it to your shell profile.

If `pyenv` is installed in your `PATH` or at `~/.pyenv`, the installer uses Python `3.12.8` from pyenv and installs all Python dependencies with pip: `opencv-python-headless`, `numpy`, `Pillow`, and `rawpy`. The installer also installs Debian desktop packages when apt is available: `python3-tk`, `tk-dev`, `xdg-utils`, and `ffmpeg`. FFmpeg applies the requested video bitrate when available. If `pyenv` is not installed, it uses native Debian packages through apt where possible and installs `rawpy` with pip. Pyenv itself may need system build dependencies the first time it compiles Python. The installer verifies that `cv2`, `numpy`, `PIL`, `rawpy`, and `tkinter` import successfully before it finishes.

From inside a cloned repository, you can run the same installer locally:

```bash
./scripts/install-debian.sh
```

Or install the native Debian packages manually:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-opencv python3-numpy python3-pillow python3-tk tk-dev xdg-utils
git clone https://github.com/Tihulu/tihulu-star-trail.git
cd tihulu-star-trail
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e . --no-deps
pip install rawpy
```

Optional pyenv setup:

```bash
sudo apt install -y python3-tk tk-dev xdg-utils
pyenv install 3.12.8
pyenv local 3.12.8
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
```

If you prefer a normal Python virtual environment, this also works on many Debian/Pop!_OS machines:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Quick Start

Open the native app from macOS Applications or the Linux application menu by launching **Tihulu Star Trail**, or from a terminal:

```bash
tihulu desktop
```

Open the local browser interface instead:

```bash
tihulu ui --open
```

Open the hosted web app:

```text
https://tihulu.github.io/tihulu-star-trail/
```

Run grouping and star-trail creation in one command:

```bash
tihulu run /media/$USER/SDCARD/DCIM ./tihulu-output
```

The output folder will look like this:

```text
tihulu-output/
  manifest.json
  groups/
    group_001/
    group_002/
  trails/
    group_001_star_trail.jpg
    group_002_star_trail.jpg
```

By default, group folders contain symlinks to your original images. Your SD card photos are not modified.

Install or refresh the Pop!_OS application launcher manually:

```bash
./scripts/install-desktop-entry.sh
```

## Useful Commands

Only group the photos:

```bash
tihulu group /media/$USER/SDCARD/DCIM ./grouped-photos
```

Create star trails from an existing grouped folder:

```bash
tihulu trail ./grouped-photos ./trails
```

Create a single star trail from one folder:

```bash
tihulu trail ./one-angle-folder ./star-trail.jpg
```

Create a timelapse video:

```bash
tihulu timelapse /media/$USER/SDCARD/DCIM ./timelapse.mp4 --fps 24
```

Create trails and one timelapse per detected group:

```bash
tihulu run /media/$USER/SDCARD/DCIM ./tihulu-output --timelapse
```

Copy files instead of creating symlinks:

```bash
tihulu run /media/$USER/SDCARD/DCIM ./tihulu-output --link-mode copy
```

## Tuning The Grouping

If photos from different angles are being mixed together, make the grouping stricter:

```bash
tihulu run ./photos ./output --threshold 0.55 --min-matches 24
```

If photos from the same angle are being split into too many groups, make it more permissive:

```bash
tihulu run ./photos ./output --threshold 0.35
```

To also keep different shooting sessions apart by metadata time, enable the optional time guard:

```bash
tihulu run ./photos ./output --time-metadata --time-window-hours 6
```

The default Linux/desktop threshold is `0.42`. The Linux grouping engine now uses mutual ORB feature matches, RANSAC homography inliers, inlier spread across the frame, and homography sanity checks before accepting a same-angle match. The optional time metadata guard uses EXIF capture time when available, then falls back to the file modified time. Set its window in hours in the desktop app, local web UI, hosted web app, or CLI with `--time-window-hours`; `--time-window-minutes` still works for older scripts. The GitHub Pages browser app uses a separate browser-only scorer with a default threshold of `0.72`; it compares luminance structure, edge layout, color balance, contrast, and aspect ratio. Its optional time metadata guard uses the browser-provided file modified time. In both apps, higher threshold values are stricter. Most real night-sky sets may still need a little tuning because foreground detail, moonlight, clouds, lens distortion, and exposure settings all affect matching.

## RAW Files

RAW support uses `rawpy` and covers common camera formats such as `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.raf`, `.pef`, `.srw`, and `.x3f`. The macOS and Debian/Pop!_OS desktop apps, local browser UI, and CLI decode RAW files through the local Python engine. The GitHub Pages app runs fully in the browser, so it skips RAW files and hidden dot files, then continues with browser-readable JPEG/PNG/WebP/BMP/GIF/AVIF photos. Use a native desktop app or local browser UI for real RAW processing.

## GitHub Pages

The static web app lives in `docs/` and is deployed by `.github/workflows/pages.yml` using GitHub Actions. The hosted app is configured for `https://tihulu.github.io/tihulu-star-trail/`. Browser exports include PNG/JPEG image quality controls, custom download names, WebM/MP4 video type, bitrate controls, and an in-page player for completed timelapse videos. The web app also includes stricter browser-side grouping, optional file-time metadata grouping, a right-corner parameter guide, and a manual group editor with a scrollable thumbnail browser, arrow-key photo navigation, undo, group renaming, manual group creation, drag-to-reorder group cards, moving photos between detected groups, and removing photos from the current working set. MP4 export uses native browser MediaRecorder support when available. Firefox commonly disables MP4 recording, so the hosted app records WebM first and can transcode it to MP4 with FFmpeg WASM; this downloads the FFmpeg core at conversion time and can be slow for large exports. The native macOS and Linux desktop apps remain the fastest reliable MP4 path.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```


The expected public repository URL is `https://github.com/Tihulu/tihulu-star-trail`.

## License

MIT License. See [LICENSE](LICENSE).
