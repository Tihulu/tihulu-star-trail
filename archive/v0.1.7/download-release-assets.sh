#!/bin/sh
set -eu

release_base="https://github.com/Tihulu/tihulu-star-trail/releases/download/v0.1.7"
archive_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
assets_dir="$archive_dir/release-assets"
mkdir -p "$assets_dir"

download_if_missing() {
  filename=$1
  if [ ! -f "$assets_dir/$filename" ]; then
    curl --fail --location --output "$assets_dir/$filename" "$release_base/$filename"
  fi
}

download_if_missing "SHA256SUMS.txt"
download_if_missing "Tihulu-Star-Trail-0.1.7-linux-x86_64-no-fuse.sh"
download_if_missing "Tihulu-Star-Trail-0.1.7-linux-x86_64.AppImage"
download_if_missing "Tihulu-Star-Trail-0.1.7-macOS-arm64.dmg"
download_if_missing "Tihulu-Star-Trail-0.1.7-macOS-x86_64.dmg"

cd "$assets_dir"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c SHA256SUMS.txt
else
  shasum -a 256 -c SHA256SUMS.txt
fi
