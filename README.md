# Tihulu Star Trail

**Hosted Web App:** https://tihulu.github.io/tihulu-star-trail/

Tihulu Star Trail is a small open source command line program for Debian-based Linux systems, including Pop!_OS. It scans a folder or SD card, groups photos that look like they were taken from the same camera angle, and creates a star trail image for each group.

The grouping step uses OpenCV feature matching and a RANSAC homography check. In plain English: it looks for visual points that agree with each other geometrically, then groups images by how likely they are to share the same viewpoint.

## Features

- Recursively scans an SD card or photo folder.
- Opens a native Debian/Pop!_OS desktop app with `tihulu desktop`.
- Keeps the local browser interface available with `tihulu ui`.
- Includes a static GitHub Pages web app for browser-readable photo sets.
- Groups images by likely camera angle.
- Writes a JSON manifest with group scores and source paths.
- Creates star trails with a lighten blend, which is the classic pixel-wise maximum stack.
- Renders MP4 timelapse videos from full folders or detected groups.
- Supports JPEG, PNG, TIFF, WebP, and common RAW formats through `rawpy`.
- Keeps the original photos untouched.
- Can organize groups as symlinks, copies, hardlinks, or manifest-only output.

## Install On Debian Or Pop!_OS

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/scripts/install-debian.sh | sh
```

The installer adds a launcher at `~/.local/bin/tihulu` and a Pop!_OS/GNOME application entry named **Tihulu Star Trail**. That launcher opens the native Linux desktop app. If `~/.local/bin` is not already on your `PATH`, run the command with the full path or add it to your shell profile.

If `pyenv` is installed in your `PATH` or at `~/.pyenv`, the installer uses Python `3.12.8` from pyenv and installs all Python dependencies with pip: `opencv-python-headless`, `numpy`, `Pillow`, and `rawpy`. The installer also installs small Debian desktop packages when apt is available: `python3-tk`, `tk-dev`, and `xdg-utils`. If `pyenv` is not installed, it uses native Debian packages through apt where possible and installs `rawpy` with pip. Pyenv itself may need system build dependencies the first time it compiles Python. The installer verifies that `cv2`, `numpy`, `PIL`, `rawpy`, and `tkinter` import successfully before it finishes.

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

Open the native app from Applications by launching **Tihulu Star Trail**, or from a terminal:

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
tihulu run ./photos ./output --threshold 0.45
```

If photos from the same angle are being split into too many groups, make it more permissive:

```bash
tihulu run ./photos ./output --threshold 0.25
```

The default threshold is `0.32`. Most real night-sky sets will need a little tuning because foreground detail, moonlight, clouds, lens distortion, and exposure settings all affect matching.

## RAW Files

RAW support uses `rawpy` and covers common camera formats such as `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.raf`, `.pef`, `.srw`, and `.x3f`. The Debian/Pop!_OS desktop app, local browser UI, and CLI decode RAW files through the local Python engine. The GitHub Pages app runs fully in the browser, so it handles browser-readable formats and downloads PNG/WebM outputs.

## GitHub Pages

The static web app lives in `docs/` and is deployed by `.github/workflows/pages.yml` using GitHub Actions. The hosted app is configured for `https://tihulu.github.io/tihulu-star-trail/`.

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

