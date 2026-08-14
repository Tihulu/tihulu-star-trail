# Native Performance Manual Test Matrix

CI validates cache limits, stale-job rejection, backend selection, CPU fallback, frame order, Python behavior, web behavior, and packaged application startup. GitHub-hosted runners do not expose representative user GPUs, so the following release-candidate checks document the physical-hardware validation path.

## Common checks

1. Open Manual Review with at least 200 JPEG/RAW photos.
2. Confirm Photo Thumbs uses compact cards and scrolling remains responsive while thumbnails appear.
3. Confirm the status line never exceeds `128/128` or `40 MB`.
4. Disable RAM cache, scroll several pages, and confirm only visible thumbnails remain referenced.
5. Disable each Thumbs option and confirm its images disappear immediately.
6. Change groups quickly while thumbnails load and confirm no image from the previous group appears.
7. Multi-select and reorder frames; confirm no visible cards flash/redecode and exported timelapse order matches the editor.
8. Run Trail and Timelapse in Auto, CPU, and GPU modes and compare the result visually.
9. Disconnect/disable the optional GPU backend where possible and confirm one fallback message appears, processing completes on CPU, and the application remains open.

## Apple Silicon macOS

- Install the ARM64 DMG on an M-series Mac with no Homebrew/Python additions.
- Confirm Auto reports the packaged backend when OpenCV exposes one, otherwise CPU.
- Confirm Activity Monitor memory stabilizes during repeated group switching and drops after thumbnails are disabled or the app closes.

## Intel macOS legacy package

- v0.1.7 is the final packaged Intel release and remains available unchanged from the archive and GitHub Releases.
- New release-candidate testing begins with v0.2.0 on Apple Silicon and Linux only.

## Linux GPU and CPU-only systems

- Run the AppImage and no-FUSE launcher on x86_64 Linux.
- On NVIDIA hardware with compatible existing drivers, confirm CUDA is used only if packaged OpenCV reports it available; no CUDA install is requested.
- On Mesa/OpenCL hardware, confirm OpenCL is used only when runtime detection and initialization succeed.
- On a CPU-only machine, confirm Auto and GPU both retain full functionality through safe CPU processing.

Minor codec and integer rounding differences are acceptable; frame order, dimensions, grouping, and visible output content must remain equivalent.
