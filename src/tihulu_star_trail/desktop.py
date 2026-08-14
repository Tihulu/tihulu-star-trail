from __future__ import annotations

import json
import queue
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
from .desktop_groups import EditableGroup, GroupWorkspace, assigned_photo
from .engine import analyze_groups, execute_action, export_groups, render_selected_group, scan_images
from .images import list_images, read_bgr
from .hardware import backend_status, detect_hardware_backend, normalize_hardware_mode
from .thumbnail_cache import (
    LRUThumbnailCache,
    ThumbnailGeneration,
    decode_thumbnail,
    estimate_image_bytes,
    prune_invisible_references,
    thumbnail_key,
)

TK_HINT = (
    "Native desktop app requires Tk. On macOS with Homebrew, run: "
    "brew install python@3.12 python-tk@3.12. "
    "On Debian/Pop!_OS, run: sudo apt install python3-tk tk-dev"
)

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
        self.cancel_requested = threading.Event()
        self.controls: list[Any] = []
        self.workspace = GroupWorkspace()
        self.selected_group = 0
        self.preview_image: Any = None
        self.output_preview_image: Any = None
        self.last_outputs: list[Path] = []
        self._drag_group_index: int | None = None
        self._drag_photo_indices: set[int] = set()
        self._drag_photo_widget: Any | None = None
        self._photo_reorder_target: tuple[int, bool] | None = None
        self.selected_photo_indices: set[int] = set()
        self._photo_selection_anchor: int | None = None
        self.current_photo_index = 0
        self.thumbnail_images: dict[int, Any] = {}
        self.photo_image_labels: list[Any | None] = []
        self.photo_tiles: list[Any] = []
        self.photo_tile_labels: list[Any] = []
        self.photo_tile_paths: list[Path] = []
        self.group_thumbnail_images: dict[str, Any] = {}
        self.thumbnail_cache: LRUThumbnailCache[tuple[str, str, int, int], Any] = LRUThumbnailCache(
            max_items=128,
            max_bytes=40 * 1024 * 1024,
        )
        self.thumbnail_generation = ThumbnailGeneration()
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tihulu-thumb")
        self.thumbnail_pending: set[tuple[int, tuple[str, str, int, int]]] = set()
        self.thumbnail_waiters: dict[
            tuple[int, tuple[str, str, int, int]], list[tuple[str, str, Path]]
        ] = {}
        self.thumbnail_futures: set[Any] = set()
        self._photo_grid_columns = 2
        self._preview_resize_after: str | None = None
        self._preview_render_key: tuple[str, int, int] | None = None
        self._video_capture: Any = None
        self._video_after: str | None = None
        self._video_playing = False

        root.title("Tihulu Star Trail")
        self._set_window_icon()
        root.geometry("1380x900")
        root.minsize(1080, 700)
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
        self.video_quality_mbps = tk.StringVar(value="8")
        self.max_side = tk.StringVar(value=str(DEFAULT_MAX_SIDE))
        self.output_max_side = tk.StringVar(value="1600")
        self.keep_original_size = tk.BooleanVar(value=False)
        self.keep_original_video_size = tk.BooleanVar(value=False)
        self.image_format = tk.StringVar(value="jpeg")
        self.video_format = tk.StringVar(value="mp4")
        self.output_name = tk.StringVar(value="tihulu-output")
        self.time_window_hours = tk.StringVar(value=str(DEFAULT_TIME_WINDOW_HOURS))
        self.link_mode = tk.StringVar(value="symlink")
        self.state = tk.StringVar(value="READY")
        self.result = tk.StringVar(value="No result yet")
        self.selected_photo_count = tk.StringVar(value="0 photos selected")
        self.photo_drag_hint = tk.StringVar(
            value="Drag photos to set timelapse order, or drop them onto another group."
        )
        self.preferences_path = self._preferences_path()
        preferences = self._load_preferences()
        self.show_photo_thumbnails = tk.BooleanVar(
            value=bool(preferences.get("show_photo_thumbnails", True))
        )
        self.show_group_thumbnails = tk.BooleanVar(
            value=bool(preferences.get("show_group_thumbnails", False))
        )
        self.cache_thumbnails_in_ram = tk.BooleanVar(
            value=bool(preferences.get("cache_thumbnails_in_ram", True))
        )
        self.hardware_acceleration = tk.StringVar(
            value=str(preferences.get("hardware_acceleration", "Auto")).title()
        )
        detected_backend = detect_hardware_backend(normalize_hardware_mode(self.hardware_acceleration.get()))
        self.processing_backend_status = tk.StringVar(value=backend_status(detected_backend))
        self.thumbnail_cache_status = tk.StringVar()
        self.photo_edit_mode = tk.BooleanVar(value=False)
        if not self.show_photo_thumbnails.get():
            self._photo_grid_columns = 1

        self._build_layout()
        self._update_thumbnail_cache_status()
        self._append_log(self.processing_backend_status.get())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        # Keep receiving the release even when the pointer leaves a thumbnail
        # while it is being dragged over the Groups list.
        self.root.bind_all("<ButtonRelease-1>", self._photo_drop, add="+")
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
        style.configure(
            "Compact.TButton",
            background=PANEL_STRONG,
            foreground=TEXT,
            bordercolor=LINE,
            focusthickness=0,
            font=("Inter", 9),
            padding=(7, 5),
        )
        style.configure(
            "Active.Compact.TButton",
            background="#34203e",
            foreground=CYAN,
            bordercolor=PINK,
            focusthickness=0,
            font=("Inter", 9, "bold"),
            padding=(7, 5),
        )
        style.configure("Primary.TButton", background=CYAN, foreground="#02040a", font=("Inter", 10, "bold"))
        style.configure("Danger.TButton", background=PANEL_STRONG, foreground=DANGER)
        style.configure(
            "Danger.Compact.TButton",
            background=PANEL_STRONG,
            foreground=DANGER,
            bordercolor=LINE,
            focusthickness=0,
            font=("Inter", 9),
            padding=(7, 5),
        )
        style.configure(
            "Groups.Treeview",
            background=FIELD,
            fieldbackground=FIELD,
            foreground=TEXT,
            borderwidth=0,
            relief="flat",
            rowheight=28,
            font=("Inter", 10),
        )
        style.map(
            "Groups.Treeview",
            background=[("selected", PINK)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Slim.Vertical.TScrollbar",
            background=PANEL_STRONG,
            troughcolor=FIELD,
            bordercolor=FIELD,
            arrowcolor=CYAN,
            relief="flat",
            width=10,
            arrowsize=9,
        )
        style.map("TButton", background=[("active", "#142133"), ("disabled", "#111827")])
        style.map("Compact.TButton", background=[("active", "#142133"), ("disabled", "#111827")])
        style.map("Active.Compact.TButton", background=[("active", "#492456")])
        style.map("Primary.TButton", background=[("active", PINK), ("disabled", "#253242")])
        style.map("TCheckbutton", foreground=[("disabled", MUTED)])
        style.map("TRadiobutton", foreground=[("disabled", MUTED)])

    def _build_layout(self) -> None:
        root_frame = self.ttk.Frame(self.root, style="App.TFrame", padding=22)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(1, weight=1)

        header = self.ttk.Frame(root_frame, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        self.ttk.Label(header, text="TIHULU DESKTOP", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        self.ttk.Label(header, text="Star Trail Forge", style="Header.TLabel").grid(row=1, column=0, sticky="w")
        info = self.ttk.Button(header, text="Info", command=self.show_info)
        info.grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 12))
        self.ttk.Label(header, textvariable=self.state, style="Status.TLabel").grid(row=0, column=2, rowspan=2, sticky="e")

        notebook = self.ttk.Notebook(root_frame)
        notebook.grid(row=1, column=0, sticky="nsew")
        process_tab = self.ttk.Frame(notebook, style="App.TFrame", padding=(0, 10, 0, 0))
        review_tab = self.ttk.Frame(notebook, style="App.TFrame", padding=(0, 10, 0, 0))
        notebook.add(process_tab, text="Process & Export")
        notebook.add(review_tab, text="Manual Review")

        process_tab.columnconfigure(0, weight=9)
        process_tab.columnconfigure(1, weight=11)
        process_tab.rowconfigure(0, weight=1)

        controls = self._panel(process_tab, 0, 0, "Controls")
        monitor = self._panel(process_tab, 0, 1, "Monitor & Output Preview")
        controls.columnconfigure(0, weight=1)
        monitor.columnconfigure(0, weight=1)
        monitor.rowconfigure(3, weight=1)

        self._mode_row(controls, 1)
        self._path_row(controls, 2, "Input Path", self.input_path, self._browse_input)
        self._path_row(controls, 3, "Output Path", self.output_path, self._browse_output)
        self._toggle_row(controls, 4)
        self._settings_grid(controls, 5)
        self._action_row(controls, 6)

        self.ttk.Label(monitor, text="Current Job", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 10))
        self.result_label = self.ttk.Label(monitor, textvariable=self.result, style="Result.TLabel", wraplength=520, justify="left")
        self.result_label.grid(row=1, column=1, sticky="e", pady=(4, 10))
        self.output_preview = self.ttk.Label(monitor, text="Completed images and videos appear here.", anchor="center")
        self.output_preview.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        preview_actions = self.ttk.Frame(monitor, style="Panel.TFrame")
        preview_actions.grid(row=2, column=0, columnspan=2, sticky="se", padx=8, pady=8)
        self.ttk.Button(preview_actions, text="Open Output", command=self.open_output).pack(side="left", padx=4)
        self.ttk.Button(preview_actions, text="Play Video", command=self.play_latest_video).pack(side="left", padx=4)
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
        self.log.grid(row=3, column=0, columnspan=2, sticky="nsew")
        scrollbar = self.ttk.Scrollbar(monitor, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=3, column=2, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set, state="disabled")
        self._append_log("Awaiting input.")
        self._build_review_tab(review_tab)

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
            ("Video Quality Mbps", self.video_quality_mbps, 0.5, 100, 0.5),
            ("Feature Side", self.max_side, 200, 4000, 50),
            ("Output Max Side", self.output_max_side, 0, 8192, 64),
            ("Time Window Hours", self.time_window_hours, 0.1, 720, 0.5),
        ]
        for index, (label, variable, from_, to, increment) in enumerate(settings):
            r, c = divmod(index, 3)
            cell = self.ttk.Frame(frame, style="Panel.TFrame")
            cell.grid(row=r * 2, column=c, sticky="ew", padx=(0, 10), pady=(0, 10))
            self.ttk.Label(cell, text=label).grid(row=0, column=0, sticky="w")
            spin = self.ttk.Spinbox(cell, textvariable=variable, from_=from_, to=to, increment=increment, width=12)
            spin.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            if label == "Output Max Side":
                self.output_max_side_control = spin
            elif label == "Video Max Side":
                self.video_max_side_control = spin
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

        format_cell = self.ttk.Frame(frame, style="Panel.TFrame")
        format_cell.grid(row=link_row, column=1, sticky="ew", padx=(0, 10), pady=(0, 10))
        self.ttk.Label(format_cell, text="Image / Video Format").grid(row=0, column=0, sticky="w")
        image_combo = self.ttk.Combobox(
            format_cell, textvariable=self.image_format, values=("jpeg", "png"), state="readonly", width=8
        )
        image_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 6))
        video_combo = self.ttk.Combobox(
            format_cell, textvariable=self.video_format, values=("mp4", "webm"), state="readonly", width=8
        )
        video_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self.controls.extend([image_combo, video_combo])

        size_cell = self.ttk.Frame(frame, style="Panel.TFrame")
        size_cell.grid(row=link_row, column=2, sticky="ew", pady=(0, 10))
        keep_original = self.ttk.Checkbutton(
            size_cell,
            text="Keep Original Size",
            variable=self.keep_original_size,
            command=self._sync_output_size,
        )
        keep_original.grid(row=0, column=0, sticky="w")
        keep_original_video = self.ttk.Checkbutton(
            size_cell,
            text="Keep Original Video Size",
            variable=self.keep_original_video_size,
            command=self._sync_output_size,
        )
        keep_original_video.grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.ttk.Label(size_cell, text="Output Name").grid(row=2, column=0, sticky="w", pady=(6, 0))
        output_name = self.ttk.Entry(size_cell, textvariable=self.output_name)
        output_name.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.controls.extend([keep_original, keep_original_video, output_name])

    def _action_row(self, parent: Any, row: int) -> None:
        frame = self.ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)
        self.scan_button = self.ttk.Button(frame, text="Scan", command=self.scan)
        self.analyze_button = self.ttk.Button(frame, text="Analyze Groups", command=self.analyze)
        self.manual_button = self.ttk.Button(frame, text="Manual Review", command=self.start_manual_review)
        self.export_button = self.ttk.Button(frame, text="Export Edited", command=self.export_edited)
        self.run_button = self.ttk.Button(frame, text="Run", command=self.run, style="Primary.TButton")
        self.stop_button = self.ttk.Button(frame, text="Stop", command=self.stop_work, style="Danger.Compact.TButton", state="disabled")
        self.open_button = self.ttk.Button(frame, text="Open Output", command=self.open_output)
        self.scan_button.grid(row=0, column=1, padx=(0, 8))
        self.analyze_button.grid(row=0, column=2, padx=(0, 8))
        self.manual_button.grid(row=0, column=3, padx=(0, 8))
        self.export_button.grid(row=0, column=4, padx=(0, 8))
        self.open_button.grid(row=0, column=5, padx=(0, 8))
        self.run_button.grid(row=0, column=6, padx=(0, 8))
        self.stop_button.grid(row=0, column=7)
        self.controls.extend([self.scan_button, self.analyze_button, self.manual_button, self.export_button, self.run_button, self.open_button])

    def _build_review_tab(self, parent: Any) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.review_panes = self.tk.PanedWindow(
            parent,
            orient="horizontal",
            bg=LINE,
            bd=0,
            relief="flat",
            sashwidth=8,
            sashpad=1,
            sashrelief="flat",
            showhandle=False,
            opaqueresize=True,
        )
        self.review_panes.grid(row=0, column=0, sticky="nsew")
        self._review_panes_initialized = False
        self.review_panes.bind(
            "<Map>",
            lambda _event: self.root.after_idle(self._set_initial_review_panes),
        )

        groups_panel = self._review_panel(self.review_panes, "Groups", width=270)
        preview_panel = self._review_panel(self.review_panes, "Photo Preview", width=620)
        photos_panel = self._review_panel(self.review_panes, "Group Photos", width=430)
        self.review_panes.add(groups_panel, minsize=170, stretch="always")
        self.review_panes.add(preview_panel, minsize=250, stretch="always")
        self.review_panes.add(photos_panel, minsize=240, stretch="always")
        self.root.after_idle(self._set_initial_review_panes)

        groups_panel.rowconfigure(1, weight=1)
        groups_panel.columnconfigure(0, weight=1)
        self.group_thumbs_button = self.ttk.Checkbutton(
            groups_panel,
            text="Thumbs",
            variable=self.show_group_thumbnails,
            command=self._toggle_group_thumbnails,
        )
        self.group_thumbs_button.grid(row=0, column=1, sticky="e", pady=(0, 8))
        self.ttk.Style(self.root).configure(
            "Groups.Treeview",
            rowheight=48 if self.show_group_thumbnails.get() else 28,
        )
        self.group_browser = self.tk.Frame(
            groups_panel,
            bg=FIELD,
            highlightthickness=2,
            highlightbackground=LINE,
            highlightcolor=CYAN,
        )
        self.group_browser.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.group_browser.rowconfigure(0, weight=1)
        self.group_browser.columnconfigure(0, weight=1)
        self.group_list = self.ttk.Treeview(
            self.group_browser,
            show="tree",
            selectmode="browse",
            style="Groups.Treeview",
        )
        self.group_list.column("#0", anchor="w", stretch=True)
        self.group_scrollbar = self.ttk.Scrollbar(
            self.group_browser,
            orient="vertical",
            command=self._group_yview,
            style="Slim.Vertical.TScrollbar",
        )
        self.group_list.configure(yscrollcommand=self.group_scrollbar.set)
        self.group_list.grid(row=0, column=0, sticky="nsew")
        self.group_scrollbar.grid(row=0, column=1, sticky="ns")
        self.group_list.bind("<<TreeviewSelect>>", self._on_group_selected)
        self.group_list.bind("<ButtonPress-1>", self._group_drag_start)
        self.group_list.bind("<B1-Motion>", self._group_drag_motion)
        self.group_list.bind(
            "<Configure>",
            lambda _event: self.root.after_idle(self._load_visible_group_thumbnails),
        )
        self._bind_mousewheel(self.group_list, self._scroll_groups)

        group_actions = self.ttk.Frame(groups_panel, style="Panel.TFrame")
        group_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        for column in range(4):
            group_actions.columnconfigure(column, weight=1)
        self.ttk.Button(group_actions, text="Add", command=self.add_group, style="Compact.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self.ttk.Button(group_actions, text="Rename", command=self.rename_group, style="Compact.TButton").grid(row=0, column=1, sticky="ew", padx=2)
        self.ttk.Button(group_actions, text="↑", command=lambda: self.reorder_group(-1), style="Compact.TButton").grid(row=0, column=2, sticky="ew", padx=2)
        self.ttk.Button(group_actions, text="↓", command=lambda: self.reorder_group(1), style="Compact.TButton").grid(row=0, column=3, sticky="ew", padx=(2, 0))

        group_exports = self.ttk.Frame(groups_panel, style="Panel.TFrame")
        group_exports.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        group_exports.columnconfigure(0, weight=1)
        group_exports.columnconfigure(1, weight=1)
        self.selected_trail_button = self.ttk.Button(
            group_exports,
            text="Trail",
            command=lambda: self.export_selected_group("trail"),
            style="Compact.TButton",
        )
        self.selected_timelapse_button = self.ttk.Button(
            group_exports,
            text="Timelapse",
            command=lambda: self.export_selected_group("timelapse"),
            style="Compact.TButton",
        )
        self.selected_trail_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.selected_timelapse_button.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.controls.extend([self.selected_trail_button, self.selected_timelapse_button])

        self.preview_panel = preview_panel
        preview_panel.rowconfigure(1, weight=1)
        preview_panel.columnconfigure(0, weight=1)
        self.photo_preview = self.ttk.Label(preview_panel, text="Analyze groups to review photos.", anchor="center")
        self.photo_preview.grid(row=1, column=0, sticky="nsew")
        self.photo_name = self.ttk.Label(preview_panel, text="", anchor="center")
        self.photo_name.grid(row=2, column=0, sticky="ew", pady=(7, 0))
        preview_actions = self.ttk.Frame(preview_panel, style="Panel.TFrame")
        preview_actions.grid(row=3, column=0, pady=(7, 0))
        self.ttk.Button(preview_actions, text="Prev", width=7, command=lambda: self.navigate_photo(-1), style="Compact.TButton").pack(side="left", padx=2)
        self.ttk.Button(preview_actions, text="Undo", width=7, command=self.undo_edit, style="Compact.TButton").pack(side="left", padx=2)
        self.ttk.Button(preview_actions, text="Next", width=7, command=lambda: self.navigate_photo(1), style="Compact.TButton").pack(side="left", padx=2)
        preview_panel.bind("<Configure>", self._schedule_preview_resize)

        photos_panel.rowconfigure(1, weight=1)
        photos_panel.columnconfigure(0, weight=1)
        photo_header_actions = self.ttk.Frame(photos_panel, style="Panel.TFrame")
        photo_header_actions.grid(row=0, column=1, sticky="e", pady=(0, 10))
        self.photo_edit_button = self.ttk.Button(
            photo_header_actions,
            text="Edit",
            command=self._toggle_photo_edit_mode,
            style="Compact.TButton",
        )
        self.photo_edit_button.pack(side="left", padx=(0, 4))
        self.photo_thumbs_button = self.ttk.Checkbutton(
            photo_header_actions,
            text="Thumbs",
            variable=self.show_photo_thumbnails,
            command=self._toggle_photo_thumbnails,
        )
        self.photo_thumbs_button.pack(side="left", padx=(0, 4))
        self.ram_cache_button = self.ttk.Checkbutton(
            photo_header_actions,
            text="RAM",
            variable=self.cache_thumbnails_in_ram,
            command=self._toggle_ram_thumbnail_cache,
        )
        self.ram_cache_button.pack(side="left", padx=(0, 4))
        self.hardware_combo = self.ttk.Combobox(
            photo_header_actions,
            textvariable=self.hardware_acceleration,
            values=("Auto", "CPU", "GPU"),
            state="readonly",
            width=5,
        )
        self.hardware_combo.pack(side="left")
        self.hardware_combo.bind("<<ComboboxSelected>>", self._hardware_acceleration_changed)
        self._add_tooltip(self.photo_edit_button, "Select or deselect multiple photos with ordinary clicks.")
        self._add_tooltip(self.photo_thumbs_button, "Show larger 180×135 photo thumbnails; turn off for filename-only mode.")
        self._add_tooltip(
            self.ram_cache_button,
            "Keeps up to 128 downscaled thumbnails (about 40 MB) for faster navigation. Turn off to reduce memory use.",
        )
        self._add_tooltip(
            self.hardware_combo,
            "Auto uses packaged acceleration when beneficial; CPU is always safe; GPU falls back to CPU if unavailable.",
        )
        photo_browser = self.ttk.Frame(photos_panel, style="Panel.TFrame")
        photo_browser.grid(row=1, column=0, columnspan=2, sticky="nsew")
        photo_browser.rowconfigure(0, weight=1)
        photo_browser.columnconfigure(0, weight=1)
        self.photo_canvas = self.tk.Canvas(
            photo_browser,
            bg=FIELD,
            highlightthickness=1,
            highlightbackground=LINE,
            bd=0,
        )
        self.photo_scrollbar = self.ttk.Scrollbar(
            photo_browser,
            orient="vertical",
            command=self.photo_canvas.yview,
            style="Slim.Vertical.TScrollbar",
        )
        self.photo_canvas.configure(yscrollcommand=self.photo_scrollbar.set)
        self.photo_canvas.grid(row=0, column=0, sticky="nsew")
        self.photo_scrollbar.grid(row=0, column=1, sticky="ns")
        self.photo_grid = self.tk.Frame(self.photo_canvas, bg=FIELD)
        self.photo_grid_window = self.photo_canvas.create_window(
            (0, 0), window=self.photo_grid, anchor="nw"
        )
        self.photo_grid.bind("<Configure>", self._sync_photo_grid_scroll)
        self.photo_canvas.bind("<Configure>", self._fit_photo_grid)
        self._bind_mousewheel(self.photo_canvas, self._scroll_photos)
        self._bind_mousewheel(self.photo_grid, self._scroll_photos)
        self.target_group = self.ttk.Combobox(photos_panel, state="readonly")
        self.target_group.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        self.photo_action_frame = self.ttk.Frame(photos_panel, style="Panel.TFrame")
        self.photo_action_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.move_photos_button = self.ttk.Button(
            self.photo_action_frame,
            text="Move",
            command=self.move_selected_photos,
            style="Compact.TButton",
        )
        self.select_all_button = self.ttk.Button(
            self.photo_action_frame,
            text="All",
            command=self.select_all_photos,
            style="Compact.TButton",
        )
        self.clear_selection_button = self.ttk.Button(
            self.photo_action_frame,
            text="Clear",
            command=self.clear_photo_selection,
            style="Compact.TButton",
        )
        self.remove_photos_button = self.ttk.Button(
            self.photo_action_frame,
            text="Remove",
            command=self.remove_selected_photos,
            style="Danger.Compact.TButton",
        )
        self.sort_name_button = self.ttk.Button(self.photo_action_frame, text="Name A–Z", command=lambda: self.sort_selected_photos("name"), style="Compact.TButton")
        self.sort_name_desc_button = self.ttk.Button(self.photo_action_frame, text="Name Z–A", command=lambda: self.sort_selected_photos("name", reverse=True), style="Compact.TButton")
        self.sort_date_button = self.ttk.Button(self.photo_action_frame, text="Date ↑", command=lambda: self.sort_selected_photos("date"), style="Compact.TButton")
        self.sort_date_desc_button = self.ttk.Button(self.photo_action_frame, text="Date ↓", command=lambda: self.sort_selected_photos("date", reverse=True), style="Compact.TButton")
        self.photo_action_buttons = [
            self.move_photos_button,
            self.select_all_button,
            self.clear_selection_button,
            self.remove_photos_button,
            self.sort_name_button,
            self.sort_name_desc_button,
            self.sort_date_button,
            self.sort_date_desc_button,
        ]
        self._layout_photo_actions(430)
        self.ttk.Label(
            photos_panel,
            textvariable=self.selected_photo_count,
            style="Result.TLabel",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.photo_drag_hint_label = self.ttk.Label(
            photos_panel,
            textvariable=self.photo_drag_hint,
            wraplength=250,
        )
        self.photo_drag_hint_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.review_compact_status = self.ttk.Label(
            photos_panel,
            textvariable=self.thumbnail_cache_status,
            font=("Inter", 8),
        )
        self.review_compact_status.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        photos_panel.bind("<Configure>", self._on_photos_panel_resize)

        self.root.bind("<Left>", lambda _event: self.navigate_photo(-1))
        self.root.bind("<Right>", lambda _event: self.navigate_photo(1))

    def _review_panel(self, parent: Any, title: str, *, width: int) -> Any:
        frame = self.ttk.Frame(
            parent,
            style="Panel.TFrame",
            padding=12,
            width=width,
        )
        self.ttk.Label(frame, text=title, style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 14)
        )
        return frame

    def _set_initial_review_panes(self) -> None:
        if self._review_panes_initialized:
            return
        total = self.review_panes.winfo_width()
        if total < 900:
            return
        left = max(170, int(total * 0.20))
        right_start = min(total - 240, max(left + 250, int(total * 0.65)))
        try:
            self.review_panes.sash_place(0, left, 1)
            self.review_panes.sash_place(1, right_start, 1)
        except self.tk.TclError:
            pass
        else:
            self._review_panes_initialized = True

    def _bind_mousewheel(self, widget: Any, callback: Callable[[Any], str]) -> None:
        widget.bind("<MouseWheel>", callback, add="+")
        widget.bind("<Button-4>", callback, add="+")
        widget.bind("<Button-5>", callback, add="+")

    def _add_tooltip(self, widget: Any, message: str) -> None:
        state: dict[str, Any] = {"window": None, "after": None}

        def show() -> None:
            if state["window"] is not None:
                return
            window = self.tk.Toplevel(self.root)
            window.wm_overrideredirect(True)
            window.configure(bg=LINE)
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            window.geometry(f"+{x}+{y}")
            self.tk.Label(
                window,
                text=message,
                bg=PANEL_STRONG,
                fg=TEXT,
                padx=8,
                pady=6,
                wraplength=300,
                justify="left",
                font=("Inter", 9),
            ).pack(padx=1, pady=1)
            state["window"] = window

        def enter(_event: Any) -> None:
            state["after"] = self.root.after(450, show)

        def leave(_event: Any) -> None:
            if state["after"] is not None:
                try:
                    self.root.after_cancel(state["after"])
                except self.tk.TclError:
                    pass
                state["after"] = None
            if state["window"] is not None:
                state["window"].destroy()
                state["window"] = None

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")

    @staticmethod
    def _wheel_units(event: Any) -> int:
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        delta = int(getattr(event, "delta", 0))
        if not delta:
            return 0
        return -1 if delta > 0 else 1

    def _scroll_groups(self, event: Any) -> str:
        units = self._wheel_units(event)
        if units:
            self.group_list.yview_scroll(units, "units")
            self.root.after_idle(self._load_visible_group_thumbnails)
        return "break"

    def _group_yview(self, *args: Any) -> None:
        self.group_list.yview(*args)
        self.root.after_idle(self._load_visible_group_thumbnails)

    def _scroll_photos(self, event: Any) -> str:
        units = self._wheel_units(event)
        if units:
            self.photo_canvas.yview_scroll(units, "units")
            self.root.after_idle(self._load_visible_photo_thumbnails)
        return "break"

    def _on_photos_panel_resize(self, event: Any) -> None:
        self._layout_photo_actions(event.width)
        self.photo_drag_hint_label.configure(wraplength=max(150, event.width - 28))

    def _layout_photo_actions(self, width: int) -> None:
        columns = 4 if width >= 520 else 2
        if getattr(self, "_photo_action_columns", None) == columns:
            return
        self._photo_action_columns = columns
        for button in self.photo_action_buttons:
            button.grid_forget()
        for column in range(4):
            self.photo_action_frame.columnconfigure(column, weight=0)
        for index, button in enumerate(self.photo_action_buttons):
            row, column = divmod(index, columns)
            button.grid(row=row, column=column, sticky="w", padx=(0, 5), pady=(0, 4))

    def _schedule_preview_resize(self, _event: Any = None) -> None:
        if self._preview_resize_after is not None:
            try:
                self.root.after_cancel(self._preview_resize_after)
            except self.tk.TclError:
                pass
        self._preview_resize_after = self.root.after(120, self._render_current_preview)

    def _sync_output_size(self) -> None:
        if hasattr(self, "output_max_side_control"):
            self.output_max_side_control.configure(
                state="disabled" if self.keep_original_size.get() else "normal"
            )
        if hasattr(self, "video_max_side_control"):
            self.video_max_side_control.configure(
                state="disabled" if self.keep_original_video_size.get() else "normal"
            )

    def _group_drag_start(self, event: Any) -> None:
        item = self.group_list.identify_row(event.y)
        self._drag_group_index = self.group_list.index(item) if item else None

    def _group_drag_motion(self, event: Any) -> None:
        if self._drag_group_index is None or not self.workspace.groups:
            return
        item = self.group_list.identify_row(event.y)
        if not item:
            return
        target = self.group_list.index(item)
        if target == self._drag_group_index:
            return
        offset = target - self._drag_group_index
        self.selected_group = self.workspace.reorder_group(self._drag_group_index, offset)
        self._drag_group_index = self.selected_group
        self._render_workspace()

    def _on_group_selected(self, _event: Any = None) -> None:
        selected = self.group_list.selection()
        if not selected:
            return
        next_group = self.group_list.index(selected[0])
        if next_group != self.selected_group:
            self.thumbnail_generation.advance()
            self._cancel_thumbnail_jobs()
            self.thumbnail_images = {}
        self.selected_group = next_group
        self._purge_photo_cache_for_current_group()
        self._render_photos()
        self.root.after_idle(self._load_visible_group_thumbnails)

    def _render_workspace(self) -> None:
        children = self.group_list.get_children()
        if children:
            self.group_list.delete(*children)
        self.group_thumbnail_images = {}
        for index, group in enumerate(self.workspace.groups):
            self.group_list.insert(
                "",
                "end",
                iid=f"group-{index}",
                text=f"{group.name}  ({len(group.photos)})",
            )
        names = [group.name for group in self.workspace.groups]
        self.target_group.configure(values=names)
        if self.workspace.groups:
            self.selected_group = min(self.selected_group, len(self.workspace.groups) - 1)
            self._select_group_row(self.selected_group)
            self.target_group.current(self.selected_group)
        self.root.after_idle(self._load_visible_group_thumbnails)
        self._render_photos()

    def _select_group_row(self, index: int) -> None:
        children = self.group_list.get_children()
        if not 0 <= index < len(children):
            return
        item = children[index]
        if self.group_list.selection() != (item,):
            self.group_list.selection_set(item)
        self.group_list.focus(item)
        self.group_list.see(item)

    def _load_visible_group_thumbnails(self) -> None:
        if not self.show_group_thumbnails.get() or not self.workspace.groups:
            return
        visible: set[str] = set()
        for item in self.group_list.get_children():
            if not self.group_list.bbox(item):
                continue
            visible.add(item)
            if item in self.group_thumbnail_images:
                continue
            index = self.group_list.index(item)
            group = self.workspace.groups[index]
            if group.photos:
                self._submit_thumbnail("group", group.photos[0].path, (48, 36), item)
        if not self.cache_thumbnails_in_ram.get():
            for item in prune_invisible_references(self.group_thumbnail_images, visible):
                if self.group_list.exists(item):
                    self.group_list.item(item, image="")

    def _toggle_group_thumbnails(self) -> None:
        self.ttk.Style(self.root).configure(
            "Groups.Treeview",
            rowheight=48 if self.show_group_thumbnails.get() else 28,
        )
        self._save_preferences()
        if not self.show_group_thumbnails.get():
            self._clear_thumbnail_cache("group")
        else:
            self.group_thumbnail_images = {}
        for item in self.group_list.get_children():
            self.group_list.item(item, image="")
        if self.show_group_thumbnails.get():
            self.root.after_idle(self._load_visible_group_thumbnails)

    def _render_photos(self, *, preserve_selection: bool = False) -> None:
        reusable_images = {
            path: self.thumbnail_images[index]
            for index, path in enumerate(self.photo_tile_paths)
            if index in self.thumbnail_images
        }
        previous_selection = set(self.selected_photo_indices) if preserve_selection else set()
        previous_current = self.current_photo_index if preserve_selection else 0
        if not preserve_selection:
            self._preview_render_key = None
        for child in self.photo_grid.winfo_children():
            child.destroy()
        self.thumbnail_images = {}
        self.photo_image_labels = []
        self.photo_tiles = []
        self.photo_tile_labels = []
        self.photo_tile_paths = []
        self.selected_photo_indices = previous_selection
        if not preserve_selection:
            self._photo_selection_anchor = None
        if not self.workspace.groups:
            self.current_photo_index = 0
            self.photo_preview.configure(image="", text="Analyze groups to review photos.")
            self.photo_name.configure(text="")
            self._refresh_photo_tile_selection()
            return
        group = self.workspace.groups[self.selected_group]
        if group.photos:
            self.current_photo_index = min(previous_current, len(group.photos) - 1)
            self.selected_photo_indices = {
                index for index in self.selected_photo_indices if index < len(group.photos)
            }
            if not preserve_selection:
                self.selected_photo_indices = {self.current_photo_index}
            for index, photo in enumerate(group.photos):
                tile = self._photo_tile(photo.path, index)
                self.photo_tiles.append(tile)
                self.photo_tile_paths.append(photo.path)
                if photo.path in reusable_images and self.photo_image_labels[index] is not None:
                    image = reusable_images[photo.path]
                    self.thumbnail_images[index] = image
                    self.photo_image_labels[index].configure(image=image, text="")
            self._layout_photo_tiles()
            self.root.after_idle(self._load_visible_photo_thumbnails)
            self._refresh_photo_tile_selection()
            self._show_photo(self.current_photo_index, preserve_selection=True)
        else:
            self.current_photo_index = 0
            self.selected_photo_indices = set()
            self.photo_preview.configure(image="", text="This group is empty.")
            self.photo_name.configure(text="")
            self._refresh_photo_tile_selection()

    def _photo_tile(self, path: Path, index: int) -> Any:
        show_thumbnail = self.show_photo_thumbnails.get()
        selected = index in self.selected_photo_indices
        tile = self.tk.Frame(
            self.photo_grid,
            bg="#123a43" if selected else PANEL_STRONG,
            highlightthickness=4,
            highlightbackground=CYAN if selected else LINE,
            highlightcolor=CYAN,
            cursor="hand2",
        )
        bound_widgets = [tile]
        if show_thumbnail:
            # Keep a real visual slot even when Tk recalculates a label from a
            # very wide source image; otherwise it collapses into a thin strip.
            thumbnail_holder = self.tk.Frame(tile, bg=FIELD, height=120)
            thumbnail_holder.pack(fill="x", padx=6, pady=(6, 2))
            thumbnail_holder.pack_propagate(False)
            image_label = self.tk.Label(
                thumbnail_holder,
                text="Loading…",
                bg=FIELD,
                fg=MUTED,
                bd=0,
            )
            image_label.pack(fill="both", expand=True)
            bound_widgets.extend([thumbnail_holder, image_label])
            self.photo_image_labels.append(image_label)
        else:
            self.photo_image_labels.append(None)
        name_label = self.tk.Label(
            tile,
            text=f"✓  {path.name}" if selected else path.name,
            bg="#123a43" if selected else PANEL_STRONG,
            fg=CYAN if selected else TEXT,
            font=("Inter", 10, "bold" if selected else "normal"),
            wraplength=196 if show_thumbnail else 360,
            justify="center" if show_thumbnail else "left",
            anchor="center" if show_thumbnail else "w",
            padx=6 if show_thumbnail else 10,
            pady=6 if show_thumbnail else 9,
        )
        name_label.pack(
            fill="x",
            padx=4,
            pady=(0, 4) if show_thumbnail else 4,
        )
        self.photo_tile_labels.append(name_label)
        bound_widgets.append(name_label)
        for widget in bound_widgets:
            widget.bind("<ButtonPress-1>", lambda event, item=index: self._photo_drag_start(event, item))
            widget.bind("<B1-Motion>", self._photo_drag_motion)
            self._bind_mousewheel(widget, self._scroll_photos)
        return tile

    def _sync_photo_grid_scroll(self, _event: Any = None) -> None:
        self.photo_canvas.configure(scrollregion=self.photo_canvas.bbox("all"))

    def _fit_photo_grid(self, event: Any) -> None:
        self.photo_canvas.itemconfigure(self.photo_grid_window, width=event.width)
        columns = 1 if not self.show_photo_thumbnails.get() else max(1, min(4, event.width // 220))
        if columns != self._photo_grid_columns:
            self._photo_grid_columns = columns
            self._layout_photo_tiles()
        self.root.after_idle(self._load_visible_photo_thumbnails)

    def _layout_photo_tiles(self) -> None:
        columns = max(1, self._photo_grid_columns)
        for column in range(5):
            self.photo_grid.columnconfigure(column, weight=1 if column < columns else 0)
        for index, tile in enumerate(self.photo_tiles):
            row, column = divmod(index, columns)
            tile.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)

    def _visible_photo_indices(self) -> set[int]:
        if not self.photo_tiles:
            return set()
        if self.photo_grid.winfo_height() <= 1 or any(tile.winfo_height() <= 1 for tile in self.photo_tiles[:1]):
            return set()
        top = self.photo_canvas.canvasy(0)
        bottom = top + self.photo_canvas.winfo_height()
        return {
            index
            for index, tile in enumerate(self.photo_tiles)
            if tile.winfo_y() + tile.winfo_height() >= top and tile.winfo_y() <= bottom
        }

    def _load_visible_photo_thumbnails(self) -> None:
        if not self.show_photo_thumbnails.get() or not self.workspace.groups:
            return
        visible = self._visible_photo_indices()
        if not visible:
            return
        photos = self.workspace.groups[self.selected_group].photos
        for index in sorted(visible):
            if index >= len(photos) or index in self.thumbnail_images:
                continue
            self._submit_thumbnail("photo", photos[index].path, (180, 120), str(index))
        if not self.cache_thumbnails_in_ram.get():
            for index in prune_invisible_references(self.thumbnail_images, visible):
                if index < len(self.photo_image_labels) and self.photo_image_labels[index] is not None:
                    self.photo_image_labels[index].configure(image="", text="Loading…")

    def _submit_thumbnail(
        self,
        kind: str,
        path: Path,
        bounds: tuple[int, int],
        identity: str,
    ) -> None:
        key = thumbnail_key(kind, path, bounds)
        generation = self.thumbnail_generation.current
        cached = self.thumbnail_cache.get(key) if self.cache_thumbnails_in_ram.get() else None
        if cached is not None:
            self._apply_thumbnail(kind, identity, path, cached, generation)
            return
        token = (generation, key)
        self.thumbnail_waiters.setdefault(token, []).append((kind, identity, Path(path)))
        if token in self.thumbnail_pending:
            return
        self.thumbnail_pending.add(token)
        future = self.thumbnail_executor.submit(decode_thumbnail, Path(path), bounds)
        self.thumbnail_futures.add(future)

        def completed(job: Any) -> None:
            self.thumbnail_futures.discard(job)
            try:
                image = job.result()
                error = None
            except Exception as failure:
                image = None
                error = str(failure)
            self.events.put(
                (
                    "thumbnail",
                    {
                        "token": token,
                        "generation": generation,
                        "path": Path(path),
                        "key": key,
                        "image": image,
                        "error": error,
                    },
                )
            )

        future.add_done_callback(completed)

    def _apply_thumbnail(
        self,
        kind: str,
        identity: str,
        path: Path,
        image: Any,
        generation: int,
    ) -> None:
        if not self.thumbnail_generation.accepts(generation):
            return
        from PIL import ImageTk

        if kind == "photo":
            index = int(identity)
            if not self.workspace.groups or index >= len(self.workspace.groups[self.selected_group].photos):
                return
            if self.workspace.groups[self.selected_group].photos[index].path != Path(path):
                return
            if index >= len(self.photo_image_labels) or self.photo_image_labels[index] is None:
                return
            tk_image = ImageTk.PhotoImage(image)
            self.thumbnail_images[index] = tk_image
            self.photo_image_labels[index].configure(image=tk_image, text="")
            return

        item = identity
        if not self.group_list.exists(item):
            return
        index = self.group_list.index(item)
        group = self.workspace.groups[index]
        if not group.photos or group.photos[0].path != Path(path):
            return
        tk_image = ImageTk.PhotoImage(image)
        self.group_thumbnail_images[item] = tk_image
        self.group_list.item(item, image=tk_image)

    def _handle_thumbnail_result(self, payload: dict[str, Any]) -> None:
        self.thumbnail_pending.discard(payload["token"])
        waiters = self.thumbnail_waiters.pop(payload["token"], [])
        if payload["error"] is not None or not self.thumbnail_generation.accepts(payload["generation"]):
            return
        image = payload["image"]
        if self.cache_thumbnails_in_ram.get():
            self.thumbnail_cache.put(payload["key"], image, estimate_image_bytes(image))
        for kind, identity, path in waiters:
            self._apply_thumbnail(kind, identity, path, image, payload["generation"])
        self._update_thumbnail_cache_status()

    def _purge_photo_cache_for_current_group(self) -> None:
        if not self.workspace.groups:
            self.thumbnail_cache.remove_where(lambda key: key[0] == "photo")
            return
        current_paths = {str(photo.path) for photo in self.workspace.groups[self.selected_group].photos}
        self.thumbnail_cache.remove_where(
            lambda key: key[0] == "photo" and key[1] not in current_paths
        )
        self._update_thumbnail_cache_status()

    def _clear_thumbnail_cache(self, kind: str | None = None) -> None:
        self.thumbnail_generation.advance()
        self._cancel_thumbnail_jobs()
        if kind is None:
            self.thumbnail_cache.clear()
        else:
            self.thumbnail_cache.remove_where(lambda key: key[0] == kind)
        if kind in {None, "photo"}:
            self.thumbnail_images = {}
            for label in self.photo_image_labels:
                if label is not None:
                    label.configure(image="", text="Loading…")
        if kind in {None, "group"}:
            self.group_thumbnail_images = {}
            if hasattr(self, "group_list"):
                for item in self.group_list.get_children():
                    self.group_list.item(item, image="")
        self._update_thumbnail_cache_status()

    def _cancel_thumbnail_jobs(self) -> None:
        for future in list(self.thumbnail_futures):
            future.cancel()
        self.thumbnail_futures.clear()
        self.thumbnail_pending.clear()
        self.thumbnail_waiters.clear()

    def _toggle_ram_thumbnail_cache(self) -> None:
        if not self.cache_thumbnails_in_ram.get():
            self.thumbnail_cache.clear()
        self._save_preferences()
        self._update_thumbnail_cache_status()
        self.root.after_idle(self._load_visible_photo_thumbnails)
        self.root.after_idle(self._load_visible_group_thumbnails)

    def _hardware_acceleration_changed(self, _event: Any = None) -> None:
        mode = normalize_hardware_mode(self.hardware_acceleration.get())
        backend = detect_hardware_backend(mode)
        self.processing_backend_status.set(backend_status(backend))
        self._append_log(self.processing_backend_status.get())
        self._save_preferences()
        self._update_thumbnail_cache_status()

    def _update_thumbnail_cache_status(self) -> None:
        if not hasattr(self, "thumbnail_cache_status"):
            return
        stats = self.thumbnail_cache.stats
        cache = (
            f"RAM cache {stats.items}/128 · {stats.bytes / (1024 * 1024):.1f}/40 MB"
            if self.cache_thumbnails_in_ram.get()
            else "RAM cache off · visible thumbnails only"
        )
        backend = self.processing_backend_status.get().replace("Hardware acceleration: ", "")
        frame = "frame —"
        if self.workspace.groups and self.workspace.groups[self.selected_group].photos:
            total = len(self.workspace.groups[self.selected_group].photos)
            frame = f"frame {min(self.current_photo_index + 1, total)}/{total}"
        self.thumbnail_cache_status.set(
            f"{frame} · {len(self.selected_photo_indices)} selected · {cache} · {backend}"
        )

    def _toggle_photo_thumbnails(self) -> None:
        self._save_preferences()
        if not self.show_photo_thumbnails.get():
            self._clear_thumbnail_cache("photo")
        self._photo_grid_columns = (
            max(1, min(4, self.photo_canvas.winfo_width() // 220))
            if self.show_photo_thumbnails.get()
            else 1
        )
        self._render_photos(preserve_selection=True)

    def _toggle_photo_edit_mode(self) -> None:
        self.photo_edit_mode.set(not self.photo_edit_mode.get())
        self._refresh_photo_tile_selection()

    def clear_photo_selection(self) -> None:
        self.selected_photo_indices = set()
        self._photo_selection_anchor = None
        self._refresh_photo_tile_selection()

    def _preferences_path(self) -> Path:
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Tihulu Star Trail" / "settings.json"
        return Path.home() / ".config" / "tihulu-star-trail" / "settings.json"

    def _load_preferences(self) -> dict[str, Any]:
        try:
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_preferences(self) -> None:
        try:
            self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
            self.preferences_path.write_text(
                json.dumps(
                    {
                        "show_photo_thumbnails": self.show_photo_thumbnails.get(),
                        "show_group_thumbnails": self.show_group_thumbnails.get(),
                        "cache_thumbnails_in_ram": self.cache_thumbnails_in_ram.get(),
                        "hardware_acceleration": self.hardware_acceleration.get(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            # Read-only homes or restricted environments should not prevent use.
            pass

    def _refresh_photo_tile_selection(self) -> None:
        for index, tile in enumerate(self.photo_tiles):
            selected = index in self.selected_photo_indices
            active = index == self.current_photo_index
            background = "#123a43" if selected else PANEL_STRONG
            tile.configure(
                bg=background,
                highlightbackground=PINK if active else CYAN if selected else LINE,
                cursor="crosshair" if self.photo_edit_mode.get() else "hand2",
            )
            for child in tile.winfo_children():
                child.configure(cursor="crosshair" if self.photo_edit_mode.get() else "hand2")
            if index < len(self.photo_tile_labels):
                name = self.workspace.groups[self.selected_group].photos[index].path.name
                prefix = "✓  " if selected else "›  " if active else ""
                self.photo_tile_labels[index].configure(
                    text=f"{prefix}{name}",
                    bg=background,
                    fg=CYAN if selected else PINK if active else TEXT,
                    font=("Inter", 10, "bold" if selected or active else "normal"),
                )
        count = len(self.selected_photo_indices)
        self.selected_photo_count.set(f"{count} photo{'s' if count != 1 else ''} selected")
        has_photos = bool(self.photo_tiles)
        has_selection = bool(self.selected_photo_indices)
        self.photo_edit_button.configure(
            text="Done" if self.photo_edit_mode.get() else "Edit",
            style="Active.Compact.TButton" if self.photo_edit_mode.get() else "Compact.TButton",
            state="normal" if has_photos else "disabled",
        )
        self.select_all_button.configure(state="normal" if has_photos else "disabled")
        self.clear_selection_button.configure(state="normal" if has_selection else "disabled")
        self.move_photos_button.configure(state="normal" if has_selection else "disabled")
        self.remove_photos_button.configure(state="normal" if has_selection else "disabled")
        self.photo_drag_hint.set(
            "Edit mode: click photos to add or remove them from the selection. Click Done to drag them."
            if self.photo_edit_mode.get()
            else "Click a photo to preview it. Use Edit for multi-select; drag photos to reorder the timelapse or move them to another group."
        )
        self._update_thumbnail_cache_status()

    def _photo_drag_start(self, event: Any, index: int) -> None:
        if self.photo_edit_mode.get():
            if index in self.selected_photo_indices:
                self.selected_photo_indices.remove(index)
            else:
                self.selected_photo_indices.add(index)
            self._photo_selection_anchor = index
            self._drag_photo_indices = set()
            self._drag_photo_widget = None
            self._show_photo(index, preserve_selection=True)
            self._refresh_photo_tile_selection()
            return
        is_shift = bool(event.state & 0x0001)
        # Ctrl on Linux/Windows and Command (Mod1/Mod2) on macOS.
        is_toggle = bool(event.state & (0x0004 | 0x0008 | 0x0010))
        # A press on an already selected card begins a block drag. Do not
        # collapse the existing multi-selection before motion is detected.
        preserve_block = index in self.selected_photo_indices and len(self.selected_photo_indices) > 1
        if preserve_block and not is_shift and not is_toggle:
            pass
        elif is_shift and self._photo_selection_anchor is not None:
            first = min(self._photo_selection_anchor, index)
            last = max(self._photo_selection_anchor, index)
            selected_range = set(range(first, last + 1))
            self.selected_photo_indices = (
                self.selected_photo_indices | selected_range
                if is_toggle
                else selected_range
            )
        elif is_toggle:
            if index in self.selected_photo_indices:
                self.selected_photo_indices.remove(index)
            else:
                self.selected_photo_indices.add(index)
            self._photo_selection_anchor = index
        else:
            self.selected_photo_indices = {index}
            self._photo_selection_anchor = index
        self._refresh_photo_tile_selection()
        self._show_photo(index, preserve_selection=True)
        self._drag_photo_indices = set(self.selected_photo_indices)
        self._drag_photo_widget = event.widget

    def _photo_drag_motion(self, event: Any) -> None:
        if self.photo_edit_mode.get():
            return
        if self._drag_photo_indices:
            if self._drag_photo_widget is not None:
                try:
                    self._drag_photo_widget.grab_set()
                except self.tk.TclError:
                    pass
            self.root.configure(cursor="fleur")
            group_target = self._group_drop_target(event.x_root, event.y_root)
            photo_target = self._photo_drop_target(event.x_root, event.y_root)
            self._clear_photo_reorder_cue()
            if group_target is not None and group_target != self.selected_group:
                self.group_browser.configure(highlightbackground=CYAN)
                self.photo_drag_hint.set(
                    f"Release to move {len(self._drag_photo_indices)} photo(s) to {self.workspace.groups[group_target].name}."
                )
            elif photo_target is not None and photo_target[0] not in self._drag_photo_indices:
                self.group_browser.configure(highlightbackground=LINE)
                self._photo_reorder_target = photo_target
                target_index, place_after = photo_target
                self.photo_tiles[target_index].configure(highlightbackground=YELLOW)
                target_name = self.workspace.groups[self.selected_group].photos[target_index].path.name
                if target_index < len(self.photo_tile_labels):
                    self.photo_tile_labels[target_index].configure(
                        text=(f"DROP AFTER ↓  {target_name}" if place_after else f"DROP BEFORE ↑  {target_name}"),
                        fg=YELLOW,
                        font=("Inter", 10, "bold"),
                    )
                self.photo_drag_hint.set(
                    f"Release to place {len(self._drag_photo_indices)} photo(s) {'after' if place_after else 'before'} {target_name}."
                )
            else:
                self.group_browser.configure(highlightbackground=LINE)
                self.photo_drag_hint.set(
                    "Drag onto another photo to set timelapse order, or onto another group to move it."
                )

    def _photo_drop(self, event: Any) -> None:
        self.root.configure(cursor="")
        moving = sorted(self._drag_photo_indices)
        self._drag_photo_indices = set()
        drag_widget = self._drag_photo_widget
        self._drag_photo_widget = None
        if drag_widget is not None:
            try:
                drag_widget.grab_release()
            except self.tk.TclError:
                pass
        self.group_browser.configure(highlightbackground=LINE)
        photo_target = self._photo_drop_target(event.x_root, event.y_root)
        self._clear_photo_reorder_cue()
        self.photo_drag_hint.set(
            "Drag photos to set timelapse order, or drop them onto another group."
        )
        if not moving or not self.workspace.groups:
            return
        target = self._group_drop_target(event.x_root, event.y_root)
        if target is not None and 0 <= target < len(self.workspace.groups) and target != self.selected_group:
            self.workspace.move_photos(self.selected_group, moving, target)
            self.selected_group = target
            self._render_workspace()
            return
        if photo_target is not None and photo_target[0] not in moving:
            photos = self.workspace.groups[self.selected_group].photos
            current_photo = photos[self.current_photo_index] if photos else None
            new_selection = self.workspace.reorder_photos(
                self.selected_group,
                moving,
                photo_target[0],
                place_after=photo_target[1],
            )
            self.selected_photo_indices = set(new_selection)
            if current_photo is not None:
                self.current_photo_index = self.workspace.groups[self.selected_group].photos.index(current_photo)
            self._render_photos(preserve_selection=True)
            return
        self._select_group_row(self.selected_group)

    def _photo_drop_target(self, x_root: int, y_root: int) -> tuple[int, bool] | None:
        for index, tile in enumerate(self.photo_tiles):
            left = tile.winfo_rootx()
            top = tile.winfo_rooty()
            width = tile.winfo_width()
            height = tile.winfo_height()
            if left <= x_root < left + width and top <= y_root < top + height:
                place_after = (
                    x_root >= left + width / 2
                    if self.show_photo_thumbnails.get()
                    else y_root >= top + height / 2
                )
                return index, place_after
        return None

    def _clear_photo_reorder_cue(self) -> None:
        if self._photo_reorder_target is None:
            return
        self._photo_reorder_target = None
        self._refresh_photo_tile_selection()

    def _group_drop_target(self, x_root: int, y_root: int) -> int | None:
        group_left = self.group_list.winfo_rootx()
        group_top = self.group_list.winfo_rooty()
        group_right = group_left + self.group_list.winfo_width()
        group_bottom = group_top + self.group_list.winfo_height()
        if not (group_left <= x_root < group_right and group_top <= y_root < group_bottom):
            return None
        item = self.group_list.identify_row(y_root - group_top)
        if not item:
            return None
        target = self.group_list.index(item)
        return target if 0 <= target < len(self.workspace.groups) else None

    def _show_photo(self, index: int, preserve_selection: bool = False) -> None:
        if not self.workspace.groups:
            return
        photos = self.workspace.groups[self.selected_group].photos
        if not photos:
            return
        index = max(0, min(index, len(photos) - 1))
        self.current_photo_index = index
        self._render_current_preview()
        self.photo_name.configure(text=f"{index + 1} / {len(photos)} — {photos[index].path.name}")
        if not preserve_selection:
            self.selected_photo_indices = {index}
        self._refresh_photo_tile_selection()

    def _render_current_preview(self) -> None:
        self._preview_resize_after = None
        if not self.workspace.groups:
            return
        photos = self.workspace.groups[self.selected_group].photos
        if not photos:
            return
        index = max(0, min(self.current_photo_index, len(photos) - 1))
        panel_width = max(120, self.preview_panel.winfo_width() - 24)
        panel_height = max(120, self.preview_panel.winfo_height() - 110)
        self.photo_name.configure(wraplength=panel_width)
        render_key = (str(photos[index].path), panel_width, panel_height)
        if render_key == self._preview_render_key:
            return
        self._preview_render_key = render_key
        try:
            self.preview_image = self._photo_image(
                photos[index].path,
                (panel_width, panel_height),
            )
        except Exception as error:
            self.photo_preview.configure(image="", text=f"Preview failed: {error}")
        else:
            self.photo_preview.configure(image=self.preview_image, text="")

    def _photo_image(self, path: Path, bounds: tuple[int, int]) -> Any:
        import cv2
        from PIL import Image, ImageTk

        bgr = read_bgr(path)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail(bounds, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    def navigate_photo(self, offset: int) -> None:
        if not self.workspace.groups or not self.workspace.groups[self.selected_group].photos:
            return
        self._show_photo(
            (self.current_photo_index + offset)
            % len(self.workspace.groups[self.selected_group].photos),
            preserve_selection=True,
        )

    def add_group(self) -> None:
        self.selected_group = self.workspace.add_group()
        self._render_workspace()

    def rename_group(self) -> None:
        if not self.workspace.groups:
            return
        from tkinter import simpledialog

        current = self.workspace.groups[self.selected_group].name
        name = simpledialog.askstring("Rename Group", "Group name:", initialvalue=current, parent=self.root)
        if name is None:
            return
        try:
            self.workspace.rename_group(self.selected_group, name)
        except ValueError as error:
            self._show_error(str(error))
        self._render_workspace()

    def reorder_group(self, offset: int) -> None:
        if not self.workspace.groups:
            return
        self.selected_group = self.workspace.reorder_group(self.selected_group, offset)
        self._render_workspace()

    def select_all_photos(self) -> None:
        if self.workspace.groups:
            self.selected_photo_indices = set(range(len(self.workspace.groups[self.selected_group].photos)))
            self._refresh_photo_tile_selection()

    def move_selected_photos(self) -> None:
        selected = sorted(self.selected_photo_indices)
        target = self.target_group.current()
        if not selected or target < 0 or target == self.selected_group:
            return
        self.workspace.move_photos(self.selected_group, selected, target)
        self._render_workspace()

    def sort_selected_photos(self, mode: str, *, reverse: bool = False) -> None:
        if not self.workspace.groups:
            return
        self.workspace.sort_photos(self.selected_group, mode, reverse=reverse)
        self.current_photo_index = 0
        self.selected_photo_indices = set()
        self._render_photos()
        direction = "descending" if reverse else "ascending"
        self._append_log(f"Sorted {self.workspace.groups[self.selected_group].name} by {mode} ({direction}); this is now the timelapse order.")

    def remove_selected_photos(self) -> None:
        selected = sorted(self.selected_photo_indices)
        if not selected:
            return
        self.workspace.remove_photos(self.selected_group, selected)
        self._render_workspace()

    def undo_edit(self) -> None:
        if self.workspace.undo():
            self._render_workspace()

    def _browse_input(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select photo folder", initialdir=self.input_path.get() or str(Path.home()))
        if selected:
            self.input_path.set(selected)
            self._clear_thumbnail_cache()

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select output folder", initialdir=str(Path.home()))
        if selected:
            self.output_path.set(selected)

    def scan(self) -> None:
        self._start_worker("scan")

    def analyze(self) -> None:
        self._clear_thumbnail_cache()
        self._start_worker("analyze")

    def start_manual_review(self) -> None:
        """Load the chosen folder into an editable group without visual analysis."""
        self._clear_thumbnail_cache()
        self._start_worker("manual")

    def export_edited(self) -> None:
        if not self.workspace.nonempty_groups():
            self._show_error("Analyze photos and keep at least one non-empty group before exporting.")
            return
        self._start_worker("export")

    def export_selected_group(self, media: str) -> None:
        if not self.workspace.groups or not self.workspace.groups[self.selected_group].photos:
            self._show_error("Select a non-empty group before exporting.")
            return
        self._start_worker(f"selected-{media}")

    def run(self) -> None:
        self._start_worker("run")

    def open_output(self) -> None:
        output = self.output_path.get().strip()
        if not output:
            self._append_log("Output path is empty.")
            return
        opener = shutil.which("open") if sys.platform == "darwin" else shutil.which("xdg-open")
        if opener is None:
            self._append_log("Could not find the system folder opener.")
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
        self.cancel_requested.clear()
        self.stop_button.configure(state="normal")
        self._set_busy(True)
        self.state.set({"scan": "SCANNING", "analyze": "ANALYZING", "manual": "LOADING", "export": "EXPORTING"}.get(mode, "RUNNING"))
        self.result.set("Working...")
        target = {
            "scan": self._scan_worker,
            "analyze": self._analyze_worker,
            "manual": self._manual_worker,
            "export": self._export_worker,
            "selected-trail": self._selected_group_worker,
            "selected-timelapse": self._selected_group_worker,
        }.get(mode, self._run_worker)
        args: tuple[Any, ...] = (payload,)
        if mode.startswith("selected-"):
            group = self.workspace.groups[self.selected_group]
            args = (payload, GroupWorkspace([group]).nonempty_groups()[0], mode)
        self.worker = threading.Thread(target=target, args=args, daemon=True)
        self.worker.start()

    def stop_work(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.cancel_requested.set()
            self.stop_button.configure(state="disabled")
            self._append_log("Stopping after the current frame…")

    def _progress(self, message: str) -> None:
        if self.cancel_requested.is_set():
            raise InterruptedError("Stopped by user.")
        self.events.put(("log", message))

    def _scan_worker(self, payload: dict[str, Any]) -> None:
        try:
            result = scan_images(payload)
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("scan", result))

    def _run_worker(self, payload: dict[str, Any]) -> None:
        try:
            result = execute_action(payload, progress=self._progress)
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("result", result))

    def _analyze_worker(self, payload: dict[str, Any]) -> None:
        try:
            groups = analyze_groups(payload, progress=self._progress)
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("groups", groups))

    def _manual_worker(self, payload: dict[str, Any]) -> None:
        try:
            paths = list_images(Path(payload["input"]), recursive=bool(payload.get("recursive", True)))
            if not paths:
                raise ValueError("No supported images found in the selected folder.")
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("manual", paths))

    def _export_worker(self, payload: dict[str, Any]) -> None:
        groups = self.workspace.nonempty_groups()
        try:
            result = export_groups(groups, payload, progress=self._progress)
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("result", result))

    def _selected_group_worker(self, payload: dict[str, Any], group: Any, mode: str) -> None:
        try:
            result = render_selected_group(
                group,
                payload,
                trail=mode == "selected-trail",
                timelapse=mode == "selected-timelapse",
                progress=self._progress,
            )
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
            "image_format": self.image_format.get(),
            "output_max_side": 0 if self.keep_original_size.get() else int(float(self.output_max_side.get())),
            "output_name": self._safe_output_name(self.output_name.get()),
            "fps": float(self.fps.get()),
            "video_max_side": 0 if self.keep_original_video_size.get() else int(float(self.video_max_side.get())),
            "video_quality_mbps": float(self.video_quality_mbps.get()),
            "max_side": int(float(self.max_side.get())),
            "time_metadata": self.time_metadata.get(),
            "time_window_hours": float(self.time_window_hours.get()),
            "link_mode": self.link_mode.get(),
            "codec": "VP90" if self.video_format.get() == "webm" else "mp4v",
            "video_extension": self.video_format.get(),
            "render_trails": True,
            "hardware_acceleration": normalize_hardware_mode(self.hardware_acceleration.get()),
        }

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(str(payload))
                if str(payload).startswith("Hardware acceleration"):
                    self.processing_backend_status.set(str(payload))
                    self._update_thumbnail_cache_status()
            elif kind == "thumbnail":
                self._handle_thumbnail_result(payload)
            elif kind == "scan":
                self._finish("READY", self._format_scan(payload))
            elif kind == "result":
                self._finish("DONE", self._format_result(payload))
                self._show_result_preview(payload)
            elif kind == "groups":
                self.workspace = GroupWorkspace.from_angle_groups(payload)
                self.selected_group = 0
                self._render_workspace()
                self._finish("READY", f"Analyzed {sum(len(group.photos) for group in payload)} photos into {len(payload)} groups. Open Manual Review to edit them.")
            elif kind == "manual":
                self.workspace = GroupWorkspace([EditableGroup("group_001", [assigned_photo(path) for path in payload])])
                self.selected_group = 0
                self._render_workspace()
                self._finish("READY", f"Loaded {len(payload)} photos into group_001 without analysis. Create groups, move frames, then export Trail or Timelapse.")
            elif kind == "error":
                if isinstance(payload, InterruptedError):
                    self._finish("STOPPED", "Stopped by user.")
                else:
                    self._finish("ERROR", str(payload))
                    self._show_error(str(payload))
        self.root.after(100, self._drain_events)

    def _finish(self, state: str, result: str) -> None:
        self.stop_button.configure(state="disabled")
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

    def _show_result_preview(self, data: dict[str, Any]) -> None:
        paths = [Path(path) for key in ("trails", "timelapses") for path in data.get(key, [])]
        self.last_outputs = paths
        image_path = next((path for path in paths if path.suffix.lower() in {".jpg", ".jpeg", ".png"}), None)
        if image_path is None:
            self.output_preview.configure(image="", text="Output completed. Use Open Output or Play Video.")
            return
        try:
            self.output_preview_image = self._photo_image(image_path, (720, 360))
        except Exception as error:
            self.output_preview.configure(image="", text=f"Preview failed: {error}")
        else:
            self.output_preview.configure(image=self.output_preview_image, text="")

    @staticmethod
    def _safe_output_name(value: str) -> str:
        safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value.strip())
        return safe.strip("-_") or "tihulu-output"

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
        if not is_busy:
            self._sync_output_size()

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

    def show_info(self) -> None:
        window = self.tk.Toplevel(self.root)
        window.title("Parameter Guide")
        window.geometry("780x650")
        window.configure(bg=BG)
        text = self.tk.Text(
            window,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="word",
            padx=22,
            pady=18,
            font=("Inter", 11),
        )
        text.pack(fill="both", expand=True, padx=16, pady=16)
        guide = """PARAMETER GUIDE

Threshold
0.30–0.38 is loose, 0.40–0.50 is balanced (0.42 default), and 0.55+ is strict and may split real sets.

Min Matches
How many recognizable details two photos must share before automatic analysis puts them in the same group. 18 is the balanced default. Lower (12–17) if one shoot is being split apart; raise (25–35+) if unrelated photos are being mixed together.

Min Frames
The minimum number of photos required to keep and export a detected group. 2 keeps every matching pair. Use 8–20 to ignore accidental tiny groups; 30+ is useful when you only want longer timelapses. Groups below this number are skipped.

Feature Side
640 is fast, 1000 is the balanced default, and 1400–2000 can find finer grouping clues but uses more memory.

Time Window Hours
2–6 separates short sessions. 8–24 can keep an overnight shoot together across midnight when Time Metadata is on.

Output Max Side
1200–1800 is good for sharing. 2400–3840 is sharper but slower and larger. Keep Original Size exports at source dimensions with no resizing or stretching.

Image Format / JPEG Quality
JPEG is smaller for sharing; PNG is lossless and larger for later editing. JPEG 80–90 keeps files small; 92–100 preserves faint trails with larger files.

Video Format / Video Max Side
MP4 is broadly compatible. WebM uses VP9 when the installed OpenCV build supports it. Video Max Side 1080–1920 is good for sharing; 2160–3840 is sharper but slower. Keep Original Video Size uses source photo dimensions with no video resizing.

FPS / Video Quality Mbps
12–18 FPS feels calm, 24 is cinematic, and 30–60 is smoother but needs more frames. 4–8 Mbps works for previews, 10–20 is cleaner, and 25+ is best for 4K-style exports.

Manual Review
Analyze Groups first. Drag the panel dividers to resize Groups, Photo Preview, and Group Photos; compact controls and thumbnail columns adapt to the available width. Photo Thumbs use fixed 180×120 visual cards and Group Thumbs use 48×36 previews; turn either off for less work, with Photo Thumbs becoming a filename-only list. Background workers decode visible thumbnails without blocking the UI. RAM cache is on by default and keeps at most 128 downscaled thumbnails / about 40 MB for faster navigation; turn it off to retain only visible UI thumbnails and reduce memory use. Auto hardware acceleration safely uses a packaged backend when available, while CPU and GPU can be selected explicitly; GPU errors log once and fall back to CPU. Click Edit to select or deselect multiple photos with normal clicks, then Done to drag them before or after another photo to set the timelapse order, or onto another group to move them. Multi-selected photos move as one block. Ctrl/Command and Shift selection also remain available. Trail stacking is order-independent, but moving or removing frames changes its result. You can rename, add, drag-reorder, move or remove photos, navigate with arrow keys, and undo up to 50 edits. Export Edited writes only non-empty groups.

Original photos are never modified.
"""
        text.insert("1.0", guide)
        text.configure(state="disabled")

    def play_latest_video(self) -> None:
        video_path = next(
            (path for path in reversed(self.last_outputs) if path.suffix.lower() in {".mp4", ".webm", ".avi"}),
            None,
        )
        if video_path is None:
            self._show_error("No completed video is available yet.")
            return
        self._open_video_player(video_path)

    def _open_video_player(self, path: Path) -> None:
        import cv2

        self._stop_video()
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            self._show_error(f"Could not open video: {path}")
            return
        self._video_capture = capture
        self._video_playing = True
        window = self.tk.Toplevel(self.root)
        window.title(f"Timelapse Player — {path.name}")
        window.geometry("900x650")
        window.configure(bg=BG)
        self.video_frame = self.ttk.Label(window, text="Loading video...", anchor="center")
        self.video_frame.pack(fill="both", expand=True, padx=12, pady=12)
        controls = self.ttk.Frame(window, style="App.TFrame")
        controls.pack(fill="x", padx=12, pady=(0, 12))
        self.video_toggle = self.ttk.Button(controls, text="Pause", command=self._toggle_video)
        self.video_toggle.pack(side="left")
        self.ttk.Button(controls, text="Restart", command=self._restart_video).pack(side="left", padx=8)
        frame_count = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
        self.video_seek = self.ttk.Scale(controls, from_=0, to=frame_count - 1, command=self._seek_video)
        self.video_seek.pack(side="left", fill="x", expand=True, padx=(8, 0))
        window.protocol("WM_DELETE_WINDOW", lambda: (self._stop_video(), window.destroy()))
        self._video_tick()

    def _video_tick(self) -> None:
        if self._video_capture is None or not self._video_playing:
            return
        import cv2
        from PIL import Image, ImageTk

        ok, frame = self._video_capture.read()
        if not ok:
            self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._video_capture.read()
        if ok:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((860, 540), Image.Resampling.LANCZOS)
            self._video_image = ImageTk.PhotoImage(image)
            self.video_frame.configure(image=self._video_image, text="")
            self.video_seek.set(self._video_capture.get(cv2.CAP_PROP_POS_FRAMES))
        fps = self._video_capture.get(cv2.CAP_PROP_FPS) or 24.0
        self._video_after = self.root.after(max(15, int(1000 / fps)), self._video_tick)

    def _toggle_video(self) -> None:
        self._video_playing = not self._video_playing
        self.video_toggle.configure(text="Pause" if self._video_playing else "Play")
        if self._video_playing:
            self._video_tick()

    def _restart_video(self) -> None:
        if self._video_capture is not None:
            import cv2

            self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if not self._video_playing:
                self._video_playing = True
                self.video_toggle.configure(text="Pause")
                self._video_tick()

    def _seek_video(self, value: str) -> None:
        if self._video_capture is not None:
            import cv2

            self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, int(float(value)))

    def _stop_video(self) -> None:
        if self._video_after is not None:
            try:
                self.root.after_cancel(self._video_after)
            except self.tk.TclError:
                pass
            self._video_after = None
        if self._video_capture is not None:
            self._video_capture.release()
            self._video_capture = None
        self._video_playing = False

    def close(self) -> None:
        self._stop_video()
        self._clear_thumbnail_cache()
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass
