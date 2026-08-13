#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer supports macOS only." >&2
  exit 1
fi

REPO_URL=${TIHULU_REPO_URL:-https://github.com/Tihulu/tihulu-star-trail.git}
DATA_DIR=${TIHULU_DATA_DIR:-$HOME/Library/Application Support/Tihulu Star Trail}
INSTALL_DIR=${TIHULU_INSTALL_DIR:-$DATA_DIR/source}
VENV_DIR=${TIHULU_VENV_DIR:-$DATA_DIR/venv}
APP_DIR=${TIHULU_APP_DIR:-$HOME/Applications}
BIN_DIR=${TIHULU_BIN_DIR:-$HOME/.local/bin}

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed. Installing it from the official Homebrew installer..."
  BREW_INSTALLER=$(mktemp "${TMPDIR:-/tmp}/tihulu-homebrew.XXXXXX")
  trap 'rm -f "$BREW_INSTALLER"' EXIT HUP INT TERM
  curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$BREW_INSTALLER"
  /bin/bash "$BREW_INSTALLER"
  rm -f "$BREW_INSTALLER"
  trap - EXIT HUP INT TERM

  if [ -x /opt/homebrew/bin/brew ]; then
    BREW_BIN=/opt/homebrew/bin/brew
  elif [ -x /usr/local/bin/brew ]; then
    BREW_BIN=/usr/local/bin/brew
  else
    echo "Homebrew installation finished, but brew could not be found." >&2
    exit 1
  fi
  eval "$($BREW_BIN shellenv)"
fi

brew install python@3.12 python-tk@3.12 ffmpeg
if ! command -v git >/dev/null 2>&1; then
  brew install git
fi
PYTHON_BIN=$(brew --prefix python@3.12)/bin/python3.12

if [ -f "pyproject.toml" ] && [ -d "src/tihulu_star_trail" ]; then
  PROJECT_DIR=$(pwd)
else
  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
  elif [ -e "$INSTALL_DIR" ]; then
    echo "Install directory exists but is not a git checkout: $INSTALL_DIR" >&2
    exit 1
  else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  PROJECT_DIR=$INSTALL_DIR
fi

venv_is_usable() {
  [ -x "$VENV_DIR/bin/python" ] || return 1
  expected=$($PYTHON_BIN -c 'import os, sys; print(os.path.realpath(sys.prefix))') || return 1
  actual=$($VENV_DIR/bin/python -c 'import os, sys; print(os.path.realpath(sys.base_prefix))') || return 1
  [ "$expected" = "$actual" ]
}

if [ -d "$VENV_DIR" ] && ! venv_is_usable; then
  echo "Rebuilding incompatible virtual environment: $VENV_DIR"
  rm -rf "$VENV_DIR"
fi
if [ ! -x "$VENV_DIR/bin/python" ]; then
  mkdir -p "$(dirname "$VENV_DIR")"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install --upgrade \
  "numpy>=1.21" \
  "opencv-python-headless>=4.5" \
  "Pillow>=9.0" \
  "rawpy>=0.19"
"$VENV_DIR/bin/python" -m pip install --no-deps --force-reinstall "$PROJECT_DIR"

"$VENV_DIR/bin/python" - <<'PYDEPS'
import importlib

modules = ("cv2", "numpy", "PIL", "rawpy", "tkinter")
missing = []
for module in modules:
    try:
        importlib.import_module(module)
    except Exception as error:
        missing.append(f"{module}: {error}")
if missing:
    raise SystemExit("Missing Tihulu dependency imports:\n" + "\n".join(missing))
print("Verified macOS dependencies: cv2, numpy, PIL, rawpy, tkinter")
PYDEPS

mkdir -p "$BIN_DIR"
{
  printf '%s\n' '#!/bin/sh'
  printf 'exec "%s" "$@"\n' "$VENV_DIR/bin/tihulu"
} > "$BIN_DIR/tihulu"
chmod 755 "$BIN_DIR/tihulu"

TIHULU_INSTALL_DIR="$PROJECT_DIR" \
TIHULU_APP_DIR="$APP_DIR" \
TIHULU_EXECUTABLE="$VENV_DIR/bin/tihulu" \
  "$PROJECT_DIR/macos/build-app.sh"

echo "Tihulu Star Trail is installed for macOS."
echo "App: $APP_DIR/Tihulu Star Trail.app"
echo "CLI: $BIN_DIR/tihulu"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tip: add $BIN_DIR to PATH to run tihulu from Terminal." ;;
esac
