#!/usr/bin/env sh
set -eu

REPO_URL=${TIHULU_REPO_URL:-https://github.com/Tihulu/tihulu-star-trail.git}
INSTALL_DIR=${TIHULU_INSTALL_DIR:-$HOME/tihulu-star-trail}
BIN_DIR=${TIHULU_BIN_DIR:-$HOME/.local/bin}
PYENV_VERSION=${TIHULU_PYTHON_VERSION:-3.12.8}

if command -v pyenv >/dev/null 2>&1; then
  if ! pyenv versions --bare | grep -qx "$PYENV_VERSION"; then
    pyenv install "$PYENV_VERSION"
  fi
  PYTHON_BIN=$(PYENV_VERSION="$PYENV_VERSION" pyenv which python)
  INSTALL_DEPS=1
else
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Install pyenv or run this on a Debian-based system with apt-get." >&2
    exit 1
  fi

  if command -v sudo >/dev/null 2>&1; then
    SUDO=sudo
  elif [ "$(id -u)" -eq 0 ]; then
    SUDO=
  else
    echo "This installer needs sudo for apt packages, or pyenv for a user-local install." >&2
    exit 1
  fi

  $SUDO apt-get update
  $SUDO apt-get install -y \
    git \
    python3 \
    python3-venv \
    python3-pip \
    python3-opencv \
    python3-numpy \
    python3-pillow

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

"$PYTHON_BIN" -m venv --system-site-packages "$PROJECT_DIR/.venv"
. "$PROJECT_DIR/.venv/bin/activate"
if [ "$INSTALL_DEPS" -eq 1 ]; then
  python -m pip install -e "$PROJECT_DIR"
else
  python -m pip install -e "$PROJECT_DIR" --no-deps
  python -m pip install rawpy
fi

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
echo "Open the interface from Applications as: Tihulu Star Trail"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tip: add $BIN_DIR to your PATH to run tihulu from any terminal." ;;
esac
