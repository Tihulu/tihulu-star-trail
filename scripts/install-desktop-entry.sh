#!/usr/bin/env sh
set -eu

APP_ID=tihulu-star-trail
PROJECT_DIR=${TIHULU_INSTALL_DIR:-$HOME/tihulu-star-trail}
BIN_DIR=${TIHULU_BIN_DIR:-$HOME/.local/bin}
ICON_SRC=${TIHULU_ICON_SRC:-$PROJECT_DIR/assets/tihulu-star-trail.svg}
DATA_HOME=${TIHULU_DATA_HOME:-$HOME/.local/share}
APP_DIR=$DATA_HOME/applications
ICON_DIR=$DATA_HOME/icons/hicolor/scalable/apps
DESKTOP_FILE=$APP_DIR/$APP_ID.desktop
ICON_DEST=$ICON_DIR/$APP_ID.svg

if [ ! -x "$BIN_DIR/tihulu" ]; then
  echo "Missing launcher: $BIN_DIR/tihulu" >&2
  echo "Run scripts/install-debian.sh first." >&2
  exit 1
fi

if [ ! -f "$ICON_SRC" ]; then
  echo "Missing icon: $ICON_SRC" >&2
  exit 1
fi

mkdir -p "$APP_DIR" "$ICON_DIR"
cp "$ICON_SRC" "$ICON_DEST"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Tihulu Star Trail
GenericName=Star Trail Processor
Comment=Group night-sky photos, build star trails, and render timelapses
Exec=$BIN_DIR/tihulu desktop
Icon=$APP_ID
Terminal=false
Categories=Graphics;Photography;
Keywords=star;trail;astrophotography;timelapse;raw;camera;
StartupNotify=true
StartupWMClass=TihuluStarTrail
EOF

chmod 644 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed Tihulu Star Trail app launcher."
echo "It should appear in Applications as: Tihulu Star Trail"
