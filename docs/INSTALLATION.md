# Operating System Installation

Tihulu Star Trail provides native desktop installation for macOS and Debian-based Linux distributions such as Debian, Ubuntu, and Pop!_OS. The hosted browser app remains available without installation at <https://tihulu.github.io/tihulu-star-trail/>.

## Supported Systems

| System | Native desktop app | Installer |
| --- | --- | --- |
| macOS 11 or newer | `Tihulu Star Trail.app` | Release DMG or `macos/install.sh` |
| Debian 12, Ubuntu 22.04, Pop!_OS 22.04, or newer | AppImage or application-menu entry | Release AppImage or `scripts/install-debian.sh` |
| Other operating systems | Use the hosted or local browser app | Manual Python installation may work but is not currently packaged |

## macOS

### Requirements

- macOS 11 or newer.
- An internet connection during the first installation.

The release DMG contains a standalone application and does not require Python or Homebrew. The one-line command installs [Homebrew](https://brew.sh/) when it is missing, then uses it to install Python 3.12, Tk, FFmpeg, Git when needed, and all Python dependencies.

### DMG Installation

1. Open the [latest GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/latest).
2. Download `arm64.dmg` for an Apple Silicon Mac, or `x86_64.dmg` for an Intel Mac.
3. Open the DMG.
4. Drag **Tihulu Star Trail** into the Applications shortcut.
5. Open the app from Applications.

Release builds are ad-hoc signed but not Apple-notarized. On the first launch, macOS may require you to Control-click **Tihulu Star Trail**, choose **Open**, and confirm the prompt.

The DMG application is standalone. The Homebrew-based method below remains useful when you also want the `tihulu` command-line launcher.

### One-Line Installation

Open Terminal and run the command below. It installs Homebrew and every required dependency when they are missing:

```sh
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/macos/install.sh | sh
```

When installation finishes, open **Tihulu Star Trail** from `~/Applications` in Finder.

### Installation From a Clone

```sh
git clone https://github.com/Tihulu/tihulu-star-trail.git
cd tihulu-star-trail
./macos/install.sh
```

Run the same command again to refresh an existing installation. To rebuild only the `.app` bundle after the runtime is already installed, run:

```sh
./macos/build-app.sh
```

### macOS Install Locations

| Component | Default location |
| --- | --- |
| Application | `~/Applications/Tihulu Star Trail.app` |
| Isolated runtime | `~/Library/Application Support/Tihulu Star Trail/venv` |
| Managed source checkout | `~/Library/Application Support/Tihulu Star Trail/source` |
| Command-line launcher | `~/.local/bin/tihulu` |
| Application log | `~/Library/Logs/Tihulu Star Trail.log` |

The app continues to work if a separate source clone is moved or deleted because the installed runtime is independent. To install the application bundle under `/Applications`, run the local installer with a writable application directory:

```sh
TIHULU_APP_DIR=/Applications ./macos/install.sh
```

macOS may request administrator permission when writing to `/Applications`.

### Verify macOS Installation

```sh
~/.local/bin/tihulu desktop --check
open "$HOME/Applications/Tihulu Star Trail.app"
```

If `tihulu` is not found without its full path, add `~/.local/bin` to your shell `PATH`.

### macOS Troubleshooting

- If automatic Homebrew installation is interrupted, rerun the same one-line installer; it detects and continues an existing Homebrew setup.
- If the app does not open, inspect `~/Library/Logs/Tihulu Star Trail.log`.
- If Tk is missing, run `brew install python@3.12 python-tk@3.12` and rerun `./macos/install.sh`.
- If video export is unavailable, run `brew install ffmpeg`.

## Debian and Pop!_OS

The same installer supports Debian-based distributions including Ubuntu and Pop!_OS.

### Requirements

- An x86_64 Debian 12, Ubuntu 22.04, Pop!_OS 22.04, or newer compatible distribution for the AppImage.
- A Debian-based Linux distribution with `apt` for the installation script.
- `sudo` access for installer-managed system packages, or an existing pyenv installation.
- An internet connection during the first installation.

### AppImage Installation

Download the `linux-x86_64.AppImage` file from the [latest GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/latest), then run:

```sh
chmod +x Tihulu-Star-Trail-*-linux-x86_64.AppImage
./Tihulu-Star-Trail-*-linux-x86_64.AppImage
```

The AppImage contains the application and Python dependencies. It does not modify the system or create an application-menu entry. Use the installation script below for managed desktop integration.

### One-Line Installation

Open a terminal and run:

```sh
curl -fsSL https://raw.githubusercontent.com/Tihulu/tihulu-star-trail/main/scripts/install-debian.sh | sh
```

The installer creates the `tihulu` launcher and a desktop application entry named **Tihulu Star Trail**.

### Installation From a Clone

```sh
git clone https://github.com/Tihulu/tihulu-star-trail.git
cd tihulu-star-trail
./scripts/install-debian.sh
```

If pyenv is available, the installer uses Python 3.12.8 and installs Python dependencies with pip. Otherwise, it installs the available native Debian packages and uses a virtual environment with system site packages.

### Debian Install Locations

| Component | Default location |
| --- | --- |
| Managed source checkout | `~/tihulu-star-trail` |
| Python environment | `~/tihulu-star-trail/.venv` |
| Command-line launcher | `~/.local/bin/tihulu` |
| Application-menu entry | `~/.local/share/applications/tihulu-star-trail.desktop` |

### Manual Debian Package Installation

```sh
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-opencv python3-numpy python3-pillow python3-tk tk-dev xdg-utils ffmpeg
git clone https://github.com/Tihulu/tihulu-star-trail.git
cd tihulu-star-trail
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e . --no-deps
pip install rawpy
```

### Verify Debian Installation

```sh
~/.local/bin/tihulu desktop --check
~/.local/bin/tihulu desktop
```

You can also launch **Tihulu Star Trail** from the application menu. If `tihulu` is not found without its full path, add `~/.local/bin` to your shell `PATH`.

### Debian Troubleshooting

- If Tk is missing, run `sudo apt install python3-tk tk-dev` and reinstall.
- If the application cannot open output folders, install `xdg-utils`.
- If video export is unavailable, install `ffmpeg`.
- If a previous virtual environment uses a different Python installation, rerun the installer; it detects and rebuilds incompatible environments.

## Start the App

After installing either native package, launch the desktop interface with:

```sh
tihulu desktop
```

To run the local browser interface instead:

```sh
tihulu ui --open
```
