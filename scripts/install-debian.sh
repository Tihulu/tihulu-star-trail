#!/usr/bin/env sh
set -eu

REPO_URL=${TIHULU_REPO_URL:-https://github.com/Tihulu/tihulu-star-trail.git}
INSTALL_DIR=${TIHULU_INSTALL_DIR:-$HOME/tihulu-star-trail}
BIN_DIR=${TIHULU_BIN_DIR:-$HOME/.local/bin}
PYENV_VERSION=${TIHULU_PYTHON_VERSION:-3.12.8}
PYENV_ROOT=${PYENV_ROOT:-$HOME/.pyenv}

apt_install() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi

  if command -v sudo >/dev/null 2>&1; then
    SUDO=sudo
  elif [ "$(id -u)" -eq 0 ]; then
    SUDO=
  else
    return 1
  fi

  $SUDO apt-get update
  $SUDO apt-get install -y "$@"
}

if ! command -v pyenv >/dev/null 2>&1 && [ -x "$PYENV_ROOT/bin/pyenv" ]; then
  export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
fi

if command -v pyenv >/dev/null 2>&1; then
  if ! apt_install git python3-tk tk-dev xdg-utils ffmpeg; then
    echo "Tip: install native desktop packages with: sudo apt install git python3-tk tk-dev xdg-utils ffmpeg" >&2
  fi

  if ! pyenv versions --bare | grep -qx "$PYENV_VERSION"; then
    pyenv install "$PYENV_VERSION"
  fi
  PYTHON_BIN=$(PYENV_VERSION="$PYENV_VERSION" pyenv which python)
  INSTALL_DEPS=1
else
  if ! apt_install \
    git \
    python3 \
    python3-venv \
    python3-pip \
    python3-opencv \
    python3-numpy \
    python3-pillow \
    python3-tk \
    tk-dev \
    ffmpeg \
    xdg-utils; then
    echo "This installer needs sudo for apt packages, or pyenv for a user-local install." >&2
    exit 1
  fi

  PYTHON_BIN=/usr/bin/python3
  INSTALL_DEPS=0
fi

if [ -f "pyproject.toml" ] && [ -d "src/tihulu_star_trail" ]; then
  PROJECT_DIR=$(pwd)
else
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to clone $REPO_URL." >&2
    exit 1
  fi

  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
  elif [ -e "$INSTALL_DIR" ]; then
    echo "Install directory already exists but is not a git checkout: $INSTALL_DIR" >&2
    exit 1
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  PROJECT_DIR=$INSTALL_DIR
fi

VENV_DIR="$PROJECT_DIR/.venv"

venv_is_usable() {
  [ -x "$VENV_DIR/bin/python" ] || return 1
  "$VENV_DIR/bin/python" -c 'import math, pathlib' >/dev/null 2>&1 || return 1

  target_prefix=$("$PYTHON_BIN" -c 'import os, sys; print(os.path.realpath(sys.prefix))') || return 1
  venv_base_prefix=$("$VENV_DIR/bin/python" -c 'import os, sys; print(os.path.realpath(sys.base_prefix))') || return 1
  [ "$venv_base_prefix" = "$target_prefix" ] || return 1

  grep -q '^include-system-site-packages = true$' "$VENV_DIR/pyvenv.cfg" || return 1
}

if [ -d "$VENV_DIR" ] && ! venv_is_usable; then
  echo "Rebuilding incompatible virtual environment: $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"
if [ "$INSTALL_DEPS" -eq 1 ]; then
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -e "$PROJECT_DIR[video]"
else
  python -m pip install -e "$PROJECT_DIR" --no-deps
  python -m pip install rawpy "imageio-ffmpeg==0.6.0"
fi

python - <<'PYDEPS'
import importlib

modules = {
    "cv2": "opencv-python-headless or python3-opencv",
    "numpy": "numpy or python3-numpy",
    "PIL": "Pillow or python3-pillow",
    "rawpy": "rawpy",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "tkinter": "python3-tk tk-dev",
}
missing = []
for module, package in modules.items():
    try:
        importlib.import_module(module)
    except Exception as error:  # pragma: no cover - install-time diagnostic
        missing.append(f"{module} ({package}): {error}")

if missing:
    raise SystemExit("Missing Tihulu dependency imports:\n" + "\n".join(missing))
print("Verified Python dependencies: cv2, numpy, PIL, rawpy, imageio-ffmpeg, tkinter")
PYDEPS

python - <<'PYVIDEO'
from tihulu_star_trail.stacker import check_video_dependencies

print(f"Verified bundled video export dependency: {check_video_dependencies(require_bundled=True)}")
PYVIDEO

mkdir -p "$BIN_DIR"
{
  printf '%s\n' '#!/usr/bin/env sh'
  printf '%s\n' ". \"$PROJECT_DIR/.venv/bin/activate\""
  printf '%s\n' 'exec tihulu "$@"'
} > "$BIN_DIR/tihulu"
chmod +x "$BIN_DIR/tihulu"

if [ -x "$PROJECT_DIR/scripts/install-desktop-entry.sh" ]; then
  TIHULU_INSTALL_DIR="$PROJECT_DIR" TIHULU_BIN_DIR="$BIN_DIR" "$PROJECT_DIR/scripts/install-desktop-entry.sh"
fi

echo "Tihulu Star Trail is installed."
echo "Try: $BIN_DIR/tihulu --help"
echo "Open the native app from Applications as: Tihulu Star Trail"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tip: add $BIN_DIR to your PATH to run tihulu from any terminal." ;;
esac
