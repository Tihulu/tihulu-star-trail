# Windows

Tihulu Star Trail is packaged for 64-bit Windows as a native desktop executable.

## Install from a GitHub Release

1. Open the latest GitHub Release.
2. Download `Tihulu-Star-Trail-<version>-windows-x86_64.exe`.
3. Double-click the executable.

The release executable bundles Python, Tk, OpenCV, RAW support, and FFmpeg. A separate Python or FFmpeg installation is not required.

The executable is currently not code-signed. Windows SmartScreen may therefore show an **Unknown publisher** warning on first launch. Verify that the file came from the official `Tihulu/tihulu-star-trail` GitHub Release before choosing to run it.

Windows settings are stored under `%LOCALAPPDATA%\Tihulu Star Trail\settings.json` when `LOCALAPPDATA` is available. The native **Open Output** button opens the selected folder in Windows Explorer.

The desktop app defaults grouped-photo output to **Copy** on Windows. Creating symbolic links on Windows can require Developer Mode or elevated privileges, so copying is the safer default. The original source photos are still left untouched.

## Build locally

Requirements:

- Windows 10 or Windows 11, x86_64
- Python 3.12
- PowerShell

From the repository root:

```powershell
python -m pip install ".[release]"
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
```

The executable is written to `release-dist\Tihulu-Star-Trail-<version>-windows-x86_64.exe`.

## Smoke checks

The release workflow runs two non-interactive checks against the packaged executable:

```powershell
$env:TIHULU_DESKTOP_CHECK = "1"
.\release-dist\Tihulu-Star-Trail-<version>-windows-x86_64.exe

$env:TIHULU_DESKTOP_CHECK = $null
$env:TIHULU_FFMPEG_CHECK = "1"
$env:TIHULU_REQUIRE_BUNDLED_FFMPEG = "1"
.\release-dist\Tihulu-Star-Trail-<version>-windows-x86_64.exe
```

These verify that the packaged Tk desktop runtime and bundled FFmpeg are usable before the artifact is uploaded.
