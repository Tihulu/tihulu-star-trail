#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
  echo "The AppImage builder must run on Linux." >&2
  exit 1
fi

PROJECT_DIR=${TIHULU_PROJECT_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
PYTHON_BIN=${TIHULU_PYTHON:-python3}
OUTPUT_DIR=${TIHULU_OUTPUT_DIR:-$PROJECT_DIR/release-dist}
VERSION=${TIHULU_VERSION:-$(PYTHONPATH="$PROJECT_DIR/src" "$PYTHON_BIN" -c 'from tihulu_star_trail import __version__; print(__version__)')}

case "$(uname -m)" in
  x86_64 | amd64) RELEASE_ARCH=x86_64 ;;
  aarch64 | arm64) RELEASE_ARCH=aarch64 ;;
  *)
    echo "Unsupported Linux architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

if ! "$PYTHON_BIN" -c 'import PyInstaller' >/dev/null 2>&1; then
  echo "PyInstaller is required. Run: python -m pip install pyinstaller" >&2
  exit 1
fi

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/tihulu-appimage.XXXXXX")
trap 'rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM
APPDIR="$TEMP_ROOT/TihuluStarTrail.AppDir"
APP_BINARY_DIR="$APPDIR/usr/bin"
APPIMAGE_FILE="$OUTPUT_DIR/Tihulu-Star-Trail-$VERSION-linux-$RELEASE_ARCH.AppImage"
ICON_SOURCE="$PROJECT_DIR/src/tihulu_star_trail/assets/tihulu-star-trail.png"

mkdir -p \
  "$OUTPUT_DIR" \
  "$APP_BINARY_DIR" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
  "$APPDIR/usr/share/metainfo"

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name tihulu-star-trail \
  --icon "$ICON_SOURCE" \
  --collect-data tihulu_star_trail \
  --collect-all rawpy \
  --hidden-import PIL.ImageTk \
  --hidden-import tkinter \
  --distpath "$TEMP_ROOT/dist" \
  --workpath "$TEMP_ROOT/work" \
  --specpath "$TEMP_ROOT/spec" \
  "$PROJECT_DIR/release/desktop_entry.py"

cp -R "$TEMP_ROOT/dist/tihulu-star-trail/." "$APP_BINARY_DIR/"
cp "$PROJECT_DIR/linux/AppRun" "$APPDIR/AppRun"
cp "$PROJECT_DIR/linux/tihulu-star-trail.desktop" "$APPDIR/tihulu-star-trail.desktop"
cp "$PROJECT_DIR/linux/tihulu-star-trail.desktop" "$APPDIR/usr/share/applications/tihulu-star-trail.desktop"
cp "$PROJECT_DIR/linux/com.tihulu.startrail.metainfo.xml" "$APPDIR/usr/share/metainfo/com.tihulu.startrail.metainfo.xml"
cp "$ICON_SOURCE" "$APPDIR/tihulu-star-trail.png"
cp "$ICON_SOURCE" "$APPDIR/usr/share/icons/hicolor/256x256/apps/tihulu-star-trail.png"
chmod +x "$APPDIR/AppRun" "$APP_BINARY_DIR/tihulu-star-trail"

if [ -n "${APPIMAGETOOL:-}" ]; then
  APPIMAGETOOL_BIN=$APPIMAGETOOL
else
  APPIMAGETOOL_BIN="$TEMP_ROOT/appimagetool-$RELEASE_ARCH.AppImage"
  curl -fsSL \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$RELEASE_ARCH.AppImage" \
    -o "$APPIMAGETOOL_BIN"
  chmod +x "$APPIMAGETOOL_BIN"
fi

rm -f "$APPIMAGE_FILE"
ARCH="$RELEASE_ARCH" VERSION="$VERSION" \
  "$APPIMAGETOOL_BIN" --appimage-extract-and-run "$APPDIR" "$APPIMAGE_FILE"
chmod +x "$APPIMAGE_FILE"

echo "Created $APPIMAGE_FILE"
sha256sum "$APPIMAGE_FILE"
