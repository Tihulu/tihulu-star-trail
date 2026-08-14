#!/bin/sh
set -eu

VERSION=0.1.2
RELEASE_URL="https://github.com/Tihulu/tihulu-star-trail/releases/download/v${VERSION}"
DOWNLOAD_DIR=${TIHULU_ARCHIVE_DOWNLOAD_DIR:-"$HOME/Downloads"}

case "$(uname -m)" in
  arm64) ARCH=arm64 ;;
  x86_64) ARCH=x86_64 ;;
  *)
    echo "Unsupported macOS architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

mkdir -p "$DOWNLOAD_DIR"
DMG="Tihulu-Star-Trail-${VERSION}-macOS-${ARCH}.dmg"
curl --fail --location --remote-name --output-dir "$DOWNLOAD_DIR" "$RELEASE_URL/$DMG"
open "$DOWNLOAD_DIR/$DMG"
echo "Opened $DMG. Drag Tihulu Star Trail to Applications to finish installation."
