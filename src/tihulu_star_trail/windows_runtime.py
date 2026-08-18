from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


def default_link_mode(platform_name: str | None = None) -> str:
    """Use copies by default on Windows, where symlinks may require extra privileges."""
    current = sys.platform if platform_name is None else platform_name
    return "copy" if current == "win32" else "symlink"


def windows_preferences_path(
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the normal per-user Windows settings location."""
    environment = os.environ if environ is None else environ
    base = environment.get("LOCALAPPDATA") or environment.get("APPDATA")
    root = Path(base) if base else (Path.home() if home is None else home) / "AppData" / "Local"
    return root / "Tihulu Star Trail" / "settings.json"


def configure_windows_runtime() -> None:
    """Apply Windows-specific desktop behavior without changing macOS/Linux paths."""
    if sys.platform != "win32":
        return

    from . import stacker
    from .desktop import TihuluDesktopApp

    if getattr(TihuluDesktopApp, "_tihulu_windows_runtime_configured", False):
        return

    original_init = TihuluDesktopApp.__init__
    original_bundled_ffmpeg = stacker.bundled_ffmpeg_executable

    def windows_init(self: TihuluDesktopApp, root: object) -> None:
        original_init(self, root)
        if self.link_mode.get() == "symlink":
            self.link_mode.set("copy")

    def preferences_path(self: TihuluDesktopApp) -> Path:
        return windows_preferences_path()

    def open_output(self: TihuluDesktopApp) -> None:
        output = self.output_path.get().strip()
        if not output:
            self._append_log("Output path is empty.")
            return
        opener = getattr(os, "startfile", None)
        if opener is None:
            self._append_log("Windows Explorer integration is unavailable.")
            return
        try:
            opener(output)
        except OSError as error:
            self._append_log(f"Could not open output folder: {error}")

    def bundled_ffmpeg_executable() -> str | None:
        try:
            import imageio_ffmpeg
        except ModuleNotFoundError:
            return None

        binaries_dir = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
        for pattern in ("ffmpeg-*.exe", "ffmpeg.exe"):
            for candidate in sorted(binaries_dir.glob(pattern)):
                if candidate.is_file():
                    return str(candidate)
        return original_bundled_ffmpeg()

    TihuluDesktopApp.__init__ = windows_init
    TihuluDesktopApp._preferences_path = preferences_path
    TihuluDesktopApp.open_output = open_output
    TihuluDesktopApp._tihulu_windows_runtime_configured = True
    stacker.bundled_ffmpeg_executable = bundled_ffmpeg_executable
