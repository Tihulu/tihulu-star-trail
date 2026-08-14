# Tihulu Star Trail v0.1.7 Archive

This folder preserves the complete **pre-performance-optimization** v0.1.7 release. It is kept separately so the working v0.1.7 application, installers, documentation, checksums, source, tag, and published GitHub Release remain available after newer versions are released.

Nothing in this archive should be replaced by a newer build.

## Included snapshot

- `tihulu-star-trail-v0.1.7-source.tar.gz` — source exactly as tagged at `v0.1.7`
- `INSTALLATION.md` — installation guide from v0.1.7
- `release-assets/SHA256SUMS.txt` — checksums published with v0.1.7
- `release-assets/Tihulu-Star-Trail-0.1.7-linux-x86_64-no-fuse.sh` — small FUSE-free launcher
- macOS ARM64/Intel DMGs and Linux AppImage are retained unchanged in the [published v0.1.7 GitHub Release](https://github.com/Tihulu/tihulu-star-trail/releases/tag/v0.1.7)

The large binary installers are also downloaded into this local archive before performance work begins. They are intentionally excluded from normal Git history because the Linux AppImage exceeds GitHub's 100 MB per-file limit. Run `./download-release-assets.sh` from this directory to restore the exact binaries into `release-assets/` on any clone. Existing matching files are verified and are not overwritten.

## Install or run v0.1.7

### macOS Apple Silicon

Download `Tihulu-Star-Trail-0.1.7-macOS-arm64.dmg`, open it, and drag the app into Applications.

### macOS Intel

Download `Tihulu-Star-Trail-0.1.7-macOS-x86_64.dmg`, open it, and drag the app into Applications.

### Linux x86_64

Download the AppImage, make it executable, and run it:

```bash
chmod +x Tihulu-Star-Trail-0.1.7-linux-x86_64.AppImage
./Tihulu-Star-Trail-0.1.7-linux-x86_64.AppImage
```

For systems without FUSE, keep the AppImage and no-FUSE launcher in the same folder, make both executable, then run the launcher.

See `INSTALLATION.md` for the full v0.1.7 setup guide.

## Integrity

After downloading, verify the original published checksums:

```bash
cd release-assets
shasum -a 256 -c SHA256SUMS.txt
```

Source snapshot SHA-256:

```text
10f6b970dbd5d2ddc33536cbac6325f0c9033ec8ae414888c195bac23215e8e3
```
