from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from .defaults import (
    DEFAULT_GROUPING_THRESHOLD,
    DEFAULT_MAX_SIDE,
    DEFAULT_MIN_MATCHES,
    DEFAULT_TIME_METADATA,
    DEFAULT_TIME_WINDOW_HOURS,
)
from .engine import execute_action, scan_images

TK_HINT = "Native desktop app requires Tk. On Debian/Pop!_OS, run: sudo apt install python3-tk tk-dev"

BG = "#05070d"
PANEL = "#0d121f"
PANEL_STRONG = "#101827"
FIELD = "#070b14"
LINE = "#284f60"
TEXT = "#f2fbff"
MUTED = "#93a8b8"
CYAN = "#43f7ff"
PINK = "#ff2bd6"
YELLOW = "#f5f25c"
GREEN = "#62ff9f"
DANGER = "#ff5b7e"
LOG_BG = "#02040a"
LOG_FG = "#ccffe2"


def check_desktop_dependencies() -> None:
    try:
        import tkinter  # noqa: F401
        from tkinter import ttk  # noqa: F401
    except (ImportError, ModuleNotFoundError) as error:
        raise RuntimeError(TK_HINT) from error


def launch_desktop() -> None:
    check_desktop_dependencies()
    import tkinter as tk
    from tkinter import messagebox

    try:
        root = tk.Tk(className="TihuluStarTrail")
    except tk.TclError as error:
        raise RuntimeError(f"Could not open the desktop window: {error}") from error

    app = TihuluDesktopApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close()


class TihuluDesktopApp:
    def __init__(self, root: Any) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.controls: list[Any] = []

        root.title("Tihulu Star Trail")
        self._set_window_icon()
        root.geometry("1180x760")
        root.minsize(980, 640)
        root.configure(bg=BG)
        self._configure_style()

        self.action = tk.StringVar(value="run")
        self.input_path = tk.StringVar(value=str(Path.home()))
        self.output_path = tk.StringVar(value=str(Path.home() / "tihulu-output"))
        self.recursive = tk.BooleanVar(value=True)
        self.include_timelapse = tk.BooleanVar(value=False)
        self.time_metadata = tk.BooleanVar(value=DEFAULT_TIME_METADATA)
        self.threshold = tk.StringVar(value=str(DEFAULT_GROUPING_THRESHOLD))
        self.min_matches = tk.StringVar(value=str(DEFAULT_MIN_MATCHES))
        self.min_frames = tk.StringVar(value="2")
        self.jpeg_quality = tk.StringVar(value="95")
        self.fps = tk.StringVar(value="24")
        self.video_max_side = tk.StringVar(value="1920")
        self.max_side = tk.StringVar(value=str(DEFAULT_MAX_SIDE))
        self.time_window_hours = tk.StringVar(value=str(DEFAULT_TIME_WINDOW_HOURS))
        self.link_mode = tk.StringVar(value="symlink")
        self.state = tk.StringVar(value="READY")
        self.result = tk.StringVar(value="No result yet")

        self._build_layout()
        self.root.after(100, self._drain_events)


    def _set_window_icon(self) -> None:
        try:
            icon_path = resources.files("tihulu_star_trail").joinpath("assets/tihulu-star-trail.png")
            icon = self.tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, icon)
            self._icon_image = icon
        except Exception:
            self._icon_image = None

    def _configure_style(self) -> None:
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass

        style.configure("App.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL, relief="flat")
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Inter", 30, "bold"))
        style.configure("Eyebrow.TLabel", background=BG, foreground=YELLOW, font=("Inter", 9, "bold"))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=TEXT, font=("Inter", 15, "bold"))
        style.configure("TLabel", background=PANEL, foreground=MUTED, font=("Inter", 10))
        style.configure("Result.TLabel", background=PANEL, foreground=GREEN, font=("Inter", 10, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=GREEN, font=("Inter", 10, "bold"))
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, bordercolor=LINE)
        style.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, arrowcolor=CYAN)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("TRadiobutton", background=PANEL, foreground=TEXT)
        style.configure("TButton", background=PANEL_STRONG, foreground=TEXT, bordercolor=LINE, focusthickness=0, padding=(14, 9))
        style.configure("Primary.TButton", background=CYAN, foreground="#02040a", font=("Inter", 10, "bold"))
        style.configure("Danger.TButton", background=PANEL_STRONG, foreground=DANGER)
        style.map("TButton", background=[("active", "#142133"), ("disabled", "#111827")])
        style.map("Primary.TButton", background=[("active", PINK), ("disabled", "#253242")])
        style.map("TCheckbutton", foreground=[("disabled", MUTED)])
        style.map("TRadiobutton", foreground=[("disabled", MUTED)])

    def _build_layout(self) -> None:
        root_frame = self.ttk.Frame(self.root, style="App.TFrame", padding=22)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=9)
        root_frame.columnconfigure(1, weight=11)
        root_frame.rowconfigure(1, weight=1)

        header = self.ttk.Frame(root_frame, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        self.ttk.Label(header, text="TIHULU DESKTOP", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        self.ttk.Label(header, text="Star Trail Forge", style="Header.TLabel").grid(row=1, column=0, sticky="w")
        self.ttk.Label(header, textvariable=self.state, style="Status.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        controls = self._panel(root_frame, 1, 0, "Controls")
        monitor = self._panel(root_frame, 1, 1, "Monitor")
        controls.columnconfigure(0, weight=1)
        monitor.columnconfigure(0, weight=1)
        monitor.rowconfigure(2, weight=1)

        self._mode_row(controls, 1)
        self._path_row(controls, 2, "Input Path", self.input_path, self._browse_input)
        self._path_row(controls, 3, "Output Path", self.output_path, self._browse_output)
        self._toggle_row(controls, 4)
        self._settings_grid(controls, 5)
        self._action_row(controls, 6)

        self.ttk.Label(monitor, text="Current Job", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 10))
        self.result_label = self.ttk.Label(monitor, textvariable=self.result, style="Result.TLabel", wraplength=520, justify="left")
        self.result_label.grid(row=1, column=1, sticky="e", pady=(4, 10))
        self.log = self.tk.Text(
            monitor,
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            height=24,
            wrap="word",
            font=("JetBrains Mono", 10),
        )
        self.log.grid(row=2, column=0, columnspan=2, sticky="nsew")
        scrollbar = self.ttk.Scrollbar(monitor, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=2, column=2, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set, state="disabled")
        self._append_log("Awaiting input.")

    def _panel(self, parent: Any, row: int, column: int, title: str) -> Any:
        frame = self.ttk.Frame(parent, style="Panel.TFrame", padding=18)
        frame.grid(row=row, column=column, sticky="nsew", padx=(0, 10) if column == 0 else (10, 0))
        self.ttk.Label(frame, text=title, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 14))
        return frame

    def _mode_row(self, parent: Any, row: int) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        for index, (value, label) in enumerate((
            ("run", "Full Run"),
            ("group", "Group"),
            ("trail", "Trail"),
            ("timelapse", "Timelapse"),
        )):
            frame.columnconfigure(index, weight=1)
            widget = self.ttk.Radiobutton(frame, text=label, value=value, variable=self.action)
            widget.grid(row=0, column=index, sticky="ew", padx=(0, 8) if index < 3 else 0)
            self.controls.append(widget)

    def _path_row(self, parent: Any, row: int, label: str, variable: Any, command: Callable[[], None]) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        self.ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        entry = self.ttk.Entry(frame, textvariable=variable)
        entry.grid(row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 8))
        button = self.ttk.Button(frame, text="Browse", command=command)
        button.grid(row=1, column=1, sticky="e", pady=(6, 0))
        self.controls.extend([entry, button])

    def _toggle_row(self, parent: Any, row: int) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        recursive = self.ttk.Checkbutton(frame, text="Recursive scan", variable=self.recursive)
        timelapse = self.ttk.Checkbutton(frame, text="Group timelapses", variable=self.include_timelapse)
        time_metadata = self.ttk.Checkbutton(frame, text="Use time metadata", variable=self.time_metadata)
        recursive.grid(row=0, column=0, sticky="w", padx=(0, 16))
        timelapse.grid(row=0, column=1, sticky="w", padx=(0, 16))
        time_metadata.grid(row=0, column=2, sticky="w")
        self.controls.extend([recursive, timelapse, time_metadata])

    def _settings_grid(self, parent: Any, row: int) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew")
        for column in range(3):
            frame.columnconfigure(column, weight=1)

        settings = [
            ("Threshold", self.threshold, 0.0, 1.0, 0.01),
            ("Min Matches", self.min_matches, 4, 200, 1),
            ("Min Frames", self.min_frames, 1, 9999, 1),
            ("JPEG Quality", self.jpeg_quality, 1, 100, 1),
            ("FPS", self.fps, 1, 120, 1),
            ("Video Max Side", self.video_max_side, 0, 8192, 64),
            ("Feature Side", self.max_side, 200, 4000, 50),
            ("Time Window Hours", self.time_window_hours, 0.1, 720, 0.5),
        ]
        for index, (label, variable, from_, to, increment) in enumerate(settings):
            r, c = divmod(index, 3)
            cell = self.ttk.Frame(frame, style="Panel.TFrame")
            cell.grid(row=r * 2, column=c, sticky="ew", padx=(0, 10), pady=(0, 10))
            self.ttk.Label(cell, text=label).grid(row=0, column=0, sticky="w")
            spin = self.ttk.Spinbox(cell, textvariable=variable, from_=from_, to=to, increment=increment, width=12)
            spin.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            self.controls.append(spin)

        cell = self.ttk.Frame(frame, style="Panel.TFrame")
        link_row = ((len(settings) + 2) // 3) * 2
        cell.grid(row=link_row, column=0, sticky="ew", padx=(0, 10), pady=(0, 10))
        self.ttk.Label(cell, text="Link Mode").grid(row=0, column=0, sticky="w")
        combo = self.ttk.Combobox(
            cell,
            textvariable=self.link_mode,
            values=("symlink", "copy", "hardlink", "none"),
            state="readonly",
        )
        combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.controls.append(combo)

    def _action_row(self, parent: Any, row: int) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)
        self.scan_button = self.ttk.Button(frame, text="Scan", command=self.scan)
        self.run_button = self.ttk.Button(frame, text="Run", command=self.run, style="Primary.TButton")
        self.open_button = self.ttk.Button(frame, text="Open Output", command=self.open_output)
        self.scan_button.grid(row=0, column=1, padx=(0, 8))
        self.open_button.grid(row=0, column=2, padx=(0, 8))
        self.run_button.grid(row=0, column=3)
        self.controls.extend([self.scan_button, self.run_button, self.open_button])

    def _browse_input(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select photo folder", initialdir=self.input_path.get() or str(Path.home()))
        if selected:
            self.input_path.set(selected)

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select output folder", initialdir=str(Path.home()))
        if selected:
            self.output_path.set(selected)

    def scan(self) -> None:
        self._start_worker("scan")

    def run(self) -> None:
        self._start_worker("run")

    def open_output(self) -> None:
        output = self.output_path.get().strip()
        if not output:
            self._append_log("Output path is empty.")
            return
        opener = shutil.which("xdg-open")
        if opener is None:
            self._append_log("xdg-open is not installed.")
            return
        try:
            subprocess.Popen([opener, output])
        except OSError as error:
            self._append_log(f"Could not open output: {error}")

    def _start_worker(self, mode: str) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        try:
            payload = self._payload()
        except ValueError as error:
            self._show_error(str(error))
            return

        self._clear_log()
        self._set_busy(True)
        self.state.set("SCANNING" if mode == "scan" else "RUNNING")
        self.result.set("Working...")
        target = self._scan_worker if mode == "scan" else self._run_worker
        self.worker = threading.Thread(target=target, args=(payload,), daemon=True)
        self.worker.start()

    def _scan_worker(self, payload: dict[str, Any]) -> None:
        try:
            result = scan_images(payload)
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("scan", result))

    def _run_worker(self, payload: dict[str, Any]) -> None:
        try:
            result = execute_action(payload, progress=lambda message: self.events.put(("log", message)))
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("result", result))

    def _payload(self) -> dict[str, Any]:
        input_path = self.input_path.get().strip()
        output_path = self.output_path.get().strip()
        if not input_path:
            raise ValueError("Input path is required")
        if not output_path:
            raise ValueError("Output path is required")
        return {
            "action": self.action.get(),
            "input": input_path,
            "output": output_path,
            "recursive": self.recursive.get(),
            "timelapse": self.include_timelapse.get(),
            "threshold": float(self.threshold.get()),
            "min_matches": int(float(self.min_matches.get())),
            "min_frames": int(float(self.min_frames.get())),
            "jpeg_quality": int(float(self.jpeg_quality.get())),
            "fps": float(self.fps.get()),
            "video_max_side": int(float(self.video_max_side.get())),
            "max_side": int(float(self.max_side.get())),
            "time_metadata": self.time_metadata.get(),
            "time_window_hours": float(self.time_window_hours.get()),
            "link_mode": self.link_mode.get(),
            "codec": "mp4v",
        }

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(str(payload))
            elif kind == "scan":
                self._finish("READY", self._format_scan(payload))
            elif kind == "result":
                self._finish("DONE", self._format_result(payload))
            elif kind == "error":
                self._finish("ERROR", str(payload))
                self._show_error(str(payload))
        self.root.after(100, self._drain_events)

    def _finish(self, state: str, result: str) -> None:
        self.state.set(state)
        self.result.set(result)
        self._append_log(result)
        self._set_busy(False)

    def _format_scan(self, data: dict[str, Any]) -> str:
        lines = [f"Images: {data.get('count', 0)}"]
        extensions = data.get("extensions", {})
        for suffix, count in sorted(extensions.items()):
            lines.append(f"{suffix}: {count}")
        return "\n".join(lines)

    def _format_result(self, data: dict[str, Any]) -> str:
        lines = []
        if "groups" in data:
            lines.append(f"Groups: {data['groups']}")
        if "trails" in data:
            lines.append(f"Trails: {len(data['trails'])}")
            lines.extend(str(path) for path in data["trails"][:3])
        if "timelapses" in data:
            lines.append(f"Timelapses: {len(data['timelapses'])}")
            lines.extend(str(path) for path in data["timelapses"][:3])
        if "manifest" in data:
            lines.append(f"Manifest: {data['manifest']}")
        return "\n".join(lines) if lines else "Done"

    def _set_busy(self, is_busy: bool) -> None:
        state = "disabled" if is_busy else "normal"
        for control in self.controls:
            try:
                if isinstance(control, self.ttk.Combobox):
                    control.configure(state="disabled" if is_busy else "readonly")
                else:
                    control.configure(state=state)
            except self.tk.TclError:
                pass

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        if self.log.index("end-1c") != "1.0":
            self.log.insert("end", "\n")
        self.log.insert("end", message)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _show_error(self, message: str) -> None:
        from tkinter import messagebox

        messagebox.showerror("Tihulu Star Trail", message)

    def close(self) -> None:
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass
