#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "The DMG builder must run on macOS." >&2
  exit 1
fi

PROJECT_DIR=${TIHULU_PROJECT_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
PYTHON_BIN=${TIHULU_PYTHON:-python3}
OUTPUT_DIR=${TIHULU_OUTPUT_DIR:-$PROJECT_DIR/release-dist}
VERSION=${TIHULU_VERSION:-$(PYTHONPATH="$PROJECT_DIR/src" "$PYTHON_BIN" -c 'from tihulu_star_trail import __version__; print(__version__)')}

case "$(uname -m)" in
  arm64) RELEASE_ARCH=arm64 ;;
  x86_64) RELEASE_ARCH=x86_64 ;;
  *)
    echo "Unsupported macOS architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

if ! "$PYTHON_BIN" -c 'import PyInstaller, imageio_ffmpeg' >/dev/null 2>&1; then
  echo "PyInstaller and imageio-ffmpeg are required. Run: python -m pip install '.[release]'" >&2
  exit 1
fi

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/tihulu-dmg.XXXXXX")
trap 'rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM
ICON_FILE="$TEMP_ROOT/TihuluStarTrail.icns"
APP_NAME="Tihulu Star Trail"
APP_BUNDLE="$TEMP_ROOT/dist/$APP_NAME.app"
DMG_ROOT="$TEMP_ROOT/dmg"
DMG_FILE="$OUTPUT_DIR/Tihulu-Star-Trail-$VERSION-macOS-$RELEASE_ARCH.dmg"

mkdir -p "$OUTPUT_DIR" "$DMG_ROOT"
sips -s format icns "$PROJECT_DIR/src/tihulu_star_trail/assets/tihulu-star-trail.png" --out "$ICON_FILE" >/dev/null

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --icon "$ICON_FILE" \
  --osx-bundle-identifier com.tihulu.startrail \
  --collect-data tihulu_star_trail \
  --collect-all rawpy \
  --collect-all imageio_ffmpeg \
  --hidden-import PIL.ImageTk \
  --hidden-import tkinter \
  --distpath "$TEMP_ROOT/dist" \
  --workpath "$TEMP_ROOT/work" \
  --specpath "$TEMP_ROOT/spec" \
  "$PROJECT_DIR/release/desktop_entry.py"

if [ ! -d "$APP_BUNDLE" ]; then
  echo "PyInstaller did not create $APP_BUNDLE" >&2
  exit 1
fi

CODESIGN_IDENTITY=${TIHULU_CODESIGN_IDENTITY:--}
if [ "$CODESIGN_IDENTITY" = "-" ]; then
  codesign --force --deep --sign - "$APP_BUNDLE"
else
  codesign --force --deep --options runtime --timestamp --sign "$CODESIGN_IDENTITY" "$APP_BUNDLE"
fi
codesign --verify --deep --strict "$APP_BUNDLE"

cp -R "$APP_BUNDLE" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"
rm -f "$DMG_FILE"
create_attempt=1
while ! hdiutil create \
  -volname "$APP_NAME $VERSION" \
  -srcfolder "$DMG_ROOT" \
  -format UDZO \
  -ov \
  "$DMG_FILE" >/dev/null; do
  if [ "$create_attempt" -ge 3 ]; then
    echo "Could not create $DMG_FILE after $create_attempt attempts." >&2
    exit 1
  fi
  echo "DMG creation was temporarily unavailable; retrying..." >&2
  rm -f "$DMG_FILE"
  create_attempt=$((create_attempt + 1))
  sleep 5
done
sync
verify_attempt=1
while ! hdiutil verify "$DMG_FILE" >/dev/null; do
  if [ "$verify_attempt" -ge 3 ]; then
    echo "Could not verify $DMG_FILE after $verify_attempt attempts." >&2
    exit 1
  fi
  echo "DMG verification was temporarily unavailable; retrying..." >&2
  verify_attempt=$((verify_attempt + 1))
  sleep 5
done

echo "Created $DMG_FILE"
shasum -a 256 "$DMG_FILE"
