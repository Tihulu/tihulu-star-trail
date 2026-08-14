#!/bin/sh
# Run the neighbouring AppImage by extracting it instead of mounting it with FUSE.
set -eu

LAUNCHER_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APPIMAGE=$(find "$LAUNCHER_DIR" -maxdepth 1 -type f -name 'Tihulu-Star-Trail-*-linux-*.AppImage' -print -quit)

if [ -z "$APPIMAGE" ]; then
  echo "Tihulu Star Trail AppImage was not found next to this launcher." >&2
  exit 1
fi

APPIMAGE_EXTRACT_AND_RUN=1 exec "$APPIMAGE" "$@"
