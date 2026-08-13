#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This app bundle builder must run on macOS." >&2
  exit 1
fi

PROJECT_DIR=${TIHULU_INSTALL_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
APP_PARENT=${TIHULU_APP_DIR:-$HOME/Applications}
APP_NAME=${TIHULU_APP_NAME:-Tihulu Star Trail}
APP_BUNDLE="$APP_PARENT/$APP_NAME.app"
EXECUTABLE=${TIHULU_EXECUTABLE:-$HOME/Library/Application Support/Tihulu Star Trail/venv/bin/tihulu}
ICON_SOURCE=${TIHULU_ICON_SOURCE:-$PROJECT_DIR/src/tihulu_star_trail/assets/tihulu-star-trail.png}
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES_DIR="$CONTENTS/Resources"
ICON_FILE="$RESOURCES_DIR/TihuluStarTrail.icns"
LAUNCHER="$MACOS_DIR/tihulu-star-trail"
LOG_DIR=${TIHULU_LOG_DIR:-$HOME/Library/Logs}
LOG_FILE="$LOG_DIR/Tihulu Star Trail.log"

if [ ! -x "$EXECUTABLE" ]; then
  echo "Missing Tihulu executable: $EXECUTABLE" >&2
  echo "Run macos/install.sh first." >&2
  exit 1
fi
if [ ! -f "$ICON_SOURCE" ]; then
  echo "Missing app icon source: $ICON_SOURCE" >&2
  exit 1
fi

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$APP_PARENT"
sips -s format icns "$ICON_SOURCE" --out "$ICON_FILE" >/dev/null

escaped_executable=$(printf '%s' "$EXECUTABLE" | sed 's/[\\"`$]/\\&/g')
escaped_log_dir=$(printf '%s' "$LOG_DIR" | sed 's/[\\"`$]/\\&/g')
escaped_log_file=$(printf '%s' "$LOG_FILE" | sed 's/[\\"`$]/\\&/g')

{
  printf '%s\n' '#!/bin/sh'
  printf '%s\n' 'export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"'
  printf 'mkdir -p "%s"\n' "$escaped_log_dir"
  printf 'exec "%s" desktop >>"%s" 2>&1\n' "$escaped_executable" "$escaped_log_file"
} > "$LAUNCHER"
chmod 755 "$LAUNCHER"

cat > "$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>
  <string>Tihulu Star Trail</string>
  <key>CFBundleExecutable</key>
  <string>tihulu-star-trail</string>
  <key>CFBundleIconFile</key>
  <string>TihuluStarTrail</string>
  <key>CFBundleIdentifier</key>
  <string>com.tihulu.startrail</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Tihulu Star Trail</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSHumanReadableCopyright</key>
  <string>MIT License</string>
</dict>
</plist>
EOF

plutil -lint "$CONTENTS/Info.plist" >/dev/null
touch "$APP_BUNDLE"
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true
fi

echo "Installed $APP_BUNDLE"
echo "Open it from Applications or run: open \"$APP_BUNDLE\""
