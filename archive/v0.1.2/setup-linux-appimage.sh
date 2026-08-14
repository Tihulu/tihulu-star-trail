#!/bin/sh
set -eu

VERSION=0.1.2
RELEASE_URL="https://github.com/Tihulu/tihulu-star-trail/releases/download/v${VERSION}"
INSTALL_DIR=${TIHULU_ARCHIVE_INSTALL_DIR:-"$HOME/Applications/Tihulu-Star-Trail-v${VERSION}"}
APPIMAGE="Tihulu-Star-Trail-${VERSION}-linux-x86_64.AppImage"
LAUNCHER="Tihulu-Star-Trail-${VERSION}-linux-x86_64-no-fuse.sh"

mkdir -p "$INSTALL_DIR"
curl --fail --location --output "$INSTALL_DIR/$APPIMAGE" "$RELEASE_URL/$APPIMAGE"
curl --fail --location --output "$INSTALL_DIR/$LAUNCHER" "$RELEASE_URL/$LAUNCHER"
chmod 755 "$INSTALL_DIR/$APPIMAGE" "$INSTALL_DIR/$LAUNCHER"
echo "Installed v${VERSION} in $INSTALL_DIR"
echo "Run $INSTALL_DIR/$APPIMAGE, or use $INSTALL_DIR/$LAUNCHER if libfuse2 is unavailable."
