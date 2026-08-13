# Tihulu Star Trail

Tihulu Star Trail is a small open source command line program for Debian-based Linux systems, including Pop!_OS. It scans a folder or SD card, groups photos that look like they were taken from the same camera angle, and creates a star trail image for each group.

The grouping step uses OpenCV feature matching and a RANSAC homography check. In plain English: it looks for visual points that agree with each other geometrically, then groups images by how likely they are to share the same viewpoint.

## Features

- Recursively scans an SD card or photo folder.
- Groups images by likely camera angle.
- Writes a JSON manifest with group scores and source paths.
- Creates star trails with a lighten blend, which is the classic pixel-wise maximum stack.
- Keeps the original photos untouched.
- Can organize groups as symlinks, copies, hardlinks, or manifest-only output.

## Install On Debian Or Pop!_OS

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/scripts/install-debian.sh | sh
```

The installer adds a launcher at `~/.local/bin/tihulu`. If that folder is not already on your `PATH`, run the command with the full path or add it to your shell profile.

From inside a cloned repository, you can run the same installer locally:

```bash
./scripts/install-debian.sh
```

Or install the native Debian packages manually:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-opencv python3-numpy python3-pillow
git clone https://github.com/Tihulu/tihulu-star-trail.git
cd tihulu-star-trail
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e . --no-deps
```

If you prefer a normal Python virtual environment, this also works on many Debian/Pop!_OS machines:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Quick Start

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

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Publish To GitHub

After creating a GitHub repository, push this project:

```bash
git init
git add .
git commit -m "Initial Tihulu star trail CLI"
git branch -M main
git remote add origin https://github.com/Tihulu/tihulu-star-trail.git
git push -u origin main
```

The expected public repository URL is `https://github.com/Tihulu/tihulu-star-trail`.

## License

MIT License. See [LICENSE](LICENSE).

