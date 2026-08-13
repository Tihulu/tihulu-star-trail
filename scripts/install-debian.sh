#!/usr/bin/env sh
set -eu

REPO_URL=${TIHULU_REPO_URL:-https://github.com/Tihulu/tihulu-star-trail.git}
INSTALL_DIR=${TIHULU_INSTALL_DIR:-$HOME/tihulu-star-trail}
BIN_DIR=${TIHULU_BIN_DIR:-$HOME/.local/bin}

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer expects a Debian-based system with apt-get." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  python3-opencv \
  python3-numpy \
  python3-pillow

if [ -f "pyproject.toml" ] && [ -d "src/tihulu_star_trail" ]; then
  PROJECT_DIR=$(pwd)
else
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

python3 -m venv --system-site-packages "$PROJECT_DIR/.venv"
. "$PROJECT_DIR/.venv/bin/activate"
pip install -e "$PROJECT_DIR" --no-deps

mkdir -p "$BIN_DIR"
{
  printf '%s\n' '#!/usr/bin/env sh'
  printf '%s\n' ". \"$PROJECT_DIR/.venv/bin/activate\""
  printf '%s\n' 'exec tihulu "$@"'
} > "$BIN_DIR/tihulu"
chmod +x "$BIN_DIR/tihulu"

echo "Tihulu Star Trail is installed."
echo "Try: $BIN_DIR/tihulu --help"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tip: add $BIN_DIR to your PATH to run tihulu from any terminal." ;;
esac
