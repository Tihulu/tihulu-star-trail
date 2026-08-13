from __future__ import annotations

import os
import sys

from tihulu_star_trail.desktop import check_desktop_dependencies, launch_desktop
from tihulu_star_trail.stacker import check_video_dependencies


def main() -> int:
    if os.environ.get("TIHULU_DESKTOP_CHECK") == "1":
        check_desktop_dependencies()
        print("Tihulu packaged desktop dependencies are available.")
        return 0
    if os.environ.get("TIHULU_FFMPEG_CHECK") == "1":
        executable = check_video_dependencies(
            require_bundled=os.environ.get("TIHULU_REQUIRE_BUNDLED_FFMPEG") == "1"
        )
        print(f"Tihulu packaged FFmpeg is available: {executable}")
        return 0

    try:
        launch_desktop()
    except Exception as error:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Tihulu Star Trail", str(error), parent=root)
            root.destroy()
        except Exception:
            print(f"Tihulu Star Trail could not start: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
