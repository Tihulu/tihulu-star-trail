from __future__ import annotations

import queue
import shutil
import subprocess
import sys
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
from .desktop_groups import GroupWorkspace
from .engine import analyze_groups, execute_action, export_groups, render_selected_group, scan_images
from .images import read_bgr

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
        self.controls: list[Any] = []
        self.workspace = GroupWorkspace()
        self.selected_group = 0
        self.preview_image: Any = None
        self.output_preview_image: Any = None
        self.last_outputs: list[Path] = []
        self._drag_group_index: int | None = None
        self._drag_photo_indices: set[int] = set()
        self._drag_photo_widget: Any | None = None
        self.selected_photo_indices: set[int] = set()
        self._photo_selection_anchor: int | None = None
        self.thumbnail_images: list[Any] = []
        self.photo_tiles: list[Any] = []
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

        self._build_layout()
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
        style.configure("Primary.TButton", background=CYAN, foreground="#02040a", font=("Inter", 10, "bold"))
        style.configure("Danger.TButton", background=PANEL_STRONG, foreground=DANGER)
        style.map("TButton", background=[("active", "#142133"), ("disabled", "#111827")])
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
        self.export_button = self.ttk.Button(frame, text="Export Edited", command=self.export_edited)
        self.run_button = self.ttk.Button(frame, text="Run", command=self.run, style="Primary.TButton")
        self.open_button = self.ttk.Button(frame, text="Open Output", command=self.open_output)
        self.scan_button.grid(row=0, column=1, padx=(0, 8))
        self.analyze_button.grid(row=0, column=2, padx=(0, 8))
        self.export_button.grid(row=0, column=3, padx=(0, 8))
        self.open_button.grid(row=0, column=4, padx=(0, 8))
        self.run_button.grid(row=0, column=5)
        self.controls.extend([self.scan_button, self.analyze_button, self.export_button, self.run_button, self.open_button])

    def _build_review_tab(self, parent: Any) -> None:
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=5)
        parent.columnconfigure(2, weight=4)
        parent.rowconfigure(0, weight=1)

        groups_panel = self._panel(parent, 0, 0, "Groups")
        groups_panel.rowconfigure(1, weight=1)
        groups_panel.columnconfigure(0, weight=1)
        self.group_list = self.tk.Listbox(
            groups_panel,
            bg=FIELD,
            fg=TEXT,
            selectbackground=PINK,
            selectforeground=TEXT,
            exportselection=False,
            activestyle="none",
        )
        self.group_list.grid(row=1, column=0, columnspan=4, sticky="nsew")
        self.group_list.bind("<<ListboxSelect>>", self._on_group_selected)
        self.group_list.bind("<ButtonPress-1>", self._group_drag_start)
        self.group_list.bind("<B1-Motion>", self._group_drag_motion)
        self.ttk.Button(groups_panel, text="Add", command=self.add_group).grid(row=2, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.ttk.Button(groups_panel, text="Rename", command=self.rename_group).grid(row=2, column=1, sticky="ew", pady=(8, 0), padx=4)
        self.ttk.Button(groups_panel, text="↑", command=lambda: self.reorder_group(-1)).grid(row=2, column=2, sticky="ew", pady=(8, 0), padx=4)
        self.ttk.Button(groups_panel, text="↓", command=lambda: self.reorder_group(1)).grid(row=2, column=3, sticky="ew", pady=(8, 0), padx=(4, 0))
        self.selected_trail_button = self.ttk.Button(
            groups_panel, text="Trail This Group", command=lambda: self.export_selected_group("trail")
        )
        self.selected_timelapse_button = self.ttk.Button(
            groups_panel, text="Timelapse This Group", command=lambda: self.export_selected_group("timelapse")
        )
        self.selected_trail_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.selected_timelapse_button.grid(row=3, column=2, columnspan=2, sticky="ew", pady=(8, 0), padx=(4, 0))
        self.controls.extend([self.selected_trail_button, self.selected_timelapse_button])

        preview_panel = self._panel(parent, 0, 1, "Photo Preview")
        preview_panel.rowconfigure(1, weight=1)
        preview_panel.columnconfigure(0, weight=1)
        self.photo_preview = self.ttk.Label(preview_panel, text="Analyze groups to review photos.", anchor="center")
        self.photo_preview.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.photo_name = self.ttk.Label(preview_panel, text="", anchor="center")
        self.photo_name.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.ttk.Button(preview_panel, text="Previous", command=lambda: self.navigate_photo(-1)).grid(row=3, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.ttk.Button(preview_panel, text="Undo", command=self.undo_edit).grid(row=3, column=1, sticky="ew", pady=(8, 0), padx=4)
        self.ttk.Button(preview_panel, text="Next", command=lambda: self.navigate_photo(1)).grid(row=3, column=2, sticky="ew", pady=(8, 0), padx=(4, 0))

        photos_panel = self._panel(parent, 0, 2, "Group Photos")
        photos_panel.rowconfigure(1, weight=1)
        photos_panel.columnconfigure(0, weight=1)
        self.photo_canvas = self.tk.Canvas(
            photos_panel,
            bg=FIELD,
            highlightthickness=1,
            highlightbackground=LINE,
            bd=0,
        )
        self.photo_scrollbar = self.ttk.Scrollbar(
            photos_panel, orient="vertical", command=self.photo_canvas.yview
        )
        self.photo_canvas.configure(yscrollcommand=self.photo_scrollbar.set)
        self.photo_canvas.grid(row=1, column=0, sticky="nsew")
        self.photo_scrollbar.grid(row=1, column=1, sticky="ns")
        self.photo_grid = self.tk.Frame(self.photo_canvas, bg=FIELD)
        self.photo_grid_window = self.photo_canvas.create_window(
            (0, 0), window=self.photo_grid, anchor="nw"
        )
        self.photo_grid.bind("<Configure>", self._sync_photo_grid_scroll)
        self.photo_canvas.bind("<Configure>", self._fit_photo_grid)
        self.target_group = self.ttk.Combobox(photos_panel, state="readonly")
        self.target_group.grid(row=2, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.ttk.Button(photos_panel, text="Move Selected", command=self.move_selected_photos).grid(row=2, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))
        self.ttk.Button(photos_panel, text="Select All", command=self.select_all_photos).grid(row=3, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.ttk.Button(photos_panel, text="Remove Selected", command=self.remove_selected_photos, style="Danger.TButton").grid(row=3, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))
        self.ttk.Label(
            photos_panel,
            text="Click a card to select. Ctrl/Command toggles cards; Shift selects a range. Drag selected cards onto a group to move them.",
            wraplength=250,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.root.bind("<Left>", lambda _event: self.navigate_photo(-1))
        self.root.bind("<Right>", lambda _event: self.navigate_photo(1))

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
        self._drag_group_index = self.group_list.nearest(event.y)

    def _group_drag_motion(self, event: Any) -> None:
        if self._drag_group_index is None or not self.workspace.groups:
            return
        target = self.group_list.nearest(event.y)
        if target == self._drag_group_index:
            return
        offset = target - self._drag_group_index
        self.selected_group = self.workspace.reorder_group(self._drag_group_index, offset)
        self._drag_group_index = self.selected_group
        self._render_workspace()

    def _on_group_selected(self, _event: Any = None) -> None:
        selected = self.group_list.curselection()
        if not selected:
            return
        self.selected_group = int(selected[0])
        self._render_photos()

    def _render_workspace(self) -> None:
        self.group_list.delete(0, "end")
        for group in self.workspace.groups:
            self.group_list.insert("end", f"{group.name}  ({len(group.photos)})")
        names = [group.name for group in self.workspace.groups]
        self.target_group.configure(values=names)
        if self.workspace.groups:
            self.selected_group = min(self.selected_group, len(self.workspace.groups) - 1)
            self.group_list.selection_set(self.selected_group)
            self.target_group.current(self.selected_group)
        self._render_photos()

    def _render_photos(self) -> None:
        for child in self.photo_grid.winfo_children():
            child.destroy()
        self.thumbnail_images = []
        self.photo_tiles = []
        self.selected_photo_indices = set()
        self._photo_selection_anchor = None
        if not self.workspace.groups:
            self.photo_preview.configure(image="", text="Analyze groups to review photos.")
            self.photo_name.configure(text="")
            return
        group = self.workspace.groups[self.selected_group]
        if group.photos:
            self.selected_photo_indices = {0}
            for index, photo in enumerate(group.photos):
                tile = self._photo_tile(photo.path, index)
                self.photo_tiles.append(tile)
                row, column = divmod(index, 2)
                tile.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
                self.photo_grid.columnconfigure(column, weight=1)
            self._show_photo(0, preserve_selection=True)
        else:
            self.photo_preview.configure(image="", text="This group is empty.")
            self.photo_name.configure(text="")

    def _photo_tile(self, path: Path, index: int) -> Any:
        try:
            image = self._photo_image(path, (180, 135))
        except Exception:
            image = None
        else:
            self.thumbnail_images.append(image)
        tile = self.tk.Label(
            self.photo_grid,
            image=image,
            text=path.name,
            compound="top",
            width=24,
            height=12 if image is not None else 8,
            wraplength=176,
            justify="center",
            bg=CYAN if index in self.selected_photo_indices else PANEL_STRONG,
            fg="#02040a" if index in self.selected_photo_indices else TEXT,
            cursor="hand2",
            padx=4,
            pady=4,
            relief="flat",
        )
        tile.bind("<ButtonPress-1>", lambda event, item=index: self._photo_drag_start(event, item))
        tile.bind("<B1-Motion>", self._photo_drag_motion)
        return tile

    def _sync_photo_grid_scroll(self, _event: Any = None) -> None:
        self.photo_canvas.configure(scrollregion=self.photo_canvas.bbox("all"))

    def _fit_photo_grid(self, event: Any) -> None:
        self.photo_canvas.itemconfigure(self.photo_grid_window, width=event.width)

    def _refresh_photo_tile_selection(self) -> None:
        for index, tile in enumerate(self.photo_tiles):
            selected = index in self.selected_photo_indices
            tile.configure(
                bg=CYAN if selected else PANEL_STRONG,
                fg="#02040a" if selected else TEXT,
            )

    def _photo_drag_start(self, event: Any, index: int) -> None:
        is_shift = bool(event.state & 0x0001)
        # Ctrl on Linux/Windows and Command (Mod1/Mod2) on macOS.
        is_toggle = bool(event.state & (0x0004 | 0x0008 | 0x0010))
        if is_shift and self._photo_selection_anchor is not None:
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

    def _photo_drag_motion(self, _event: Any) -> None:
        if self._drag_photo_indices:
            if self._drag_photo_widget is not None:
                try:
                    self._drag_photo_widget.grab_set()
                except self.tk.TclError:
                    pass
            self.root.configure(cursor="fleur")

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
        if not moving or not self.workspace.groups:
            return
        group_left = self.group_list.winfo_rootx()
        group_top = self.group_list.winfo_rooty()
        group_right = group_left + self.group_list.winfo_width()
        group_bottom = group_top + self.group_list.winfo_height()
        if not (group_left <= event.x_root < group_right and group_top <= event.y_root < group_bottom):
            return
        target = self.group_list.nearest(event.y_root - group_top)
        if target < 0 or target >= len(self.workspace.groups) or target == self.selected_group:
            return
        self.workspace.move_photos(self.selected_group, moving, target)
        self.selected_group = target
        self._render_workspace()

    def _show_photo(self, index: int, preserve_selection: bool = False) -> None:
        if not self.workspace.groups:
            return
        photos = self.workspace.groups[self.selected_group].photos
        if not photos:
            return
        index = max(0, min(index, len(photos) - 1))
        try:
            self.preview_image = self._photo_image(photos[index].path, (660, 560))
        except Exception as error:
            self.photo_preview.configure(image="", text=f"Preview failed: {error}")
        else:
            self.photo_preview.configure(image=self.preview_image, text="")
        self.photo_name.configure(text=f"{index + 1} / {len(photos)} — {photos[index].path.name}")
        if not preserve_selection:
            self.selected_photo_indices = {index}
            self._refresh_photo_tile_selection()

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
        current = min(self.selected_photo_indices) if self.selected_photo_indices else 0
        self._show_photo((current + offset) % len(self.workspace.groups[self.selected_group].photos))

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

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select output folder", initialdir=str(Path.home()))
        if selected:
            self.output_path.set(selected)

    def scan(self) -> None:
        self._start_worker("scan")

    def analyze(self) -> None:
        self._start_worker("analyze")

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
        self._set_busy(True)
        self.state.set({"scan": "SCANNING", "analyze": "ANALYZING", "export": "EXPORTING"}.get(mode, "RUNNING"))
        self.result.set("Working...")
        target = {
            "scan": self._scan_worker,
            "analyze": self._analyze_worker,
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

    def _analyze_worker(self, payload: dict[str, Any]) -> None:
        try:
            groups = analyze_groups(payload, progress=lambda message: self.events.put(("log", message)))
        except Exception as error:
            self.events.put(("error", error))
        else:
            self.events.put(("groups", groups))

    def _export_worker(self, payload: dict[str, Any]) -> None:
        groups = self.workspace.nonempty_groups()
        try:
            result = export_groups(groups, payload, progress=lambda message: self.events.put(("log", message)))
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
                progress=lambda message: self.events.put(("log", message)),
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
                self._show_result_preview(payload)
            elif kind == "groups":
                self.workspace = GroupWorkspace.from_angle_groups(payload)
                self.selected_group = 0
                self._render_workspace()
                self._finish("READY", f"Analyzed {sum(len(group.photos) for group in payload)} photos into {len(payload)} groups. Open Manual Review to edit them.")
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
Higher values make grouping stricter. Lower values keep more visually similar photos together.

Min Matches
The minimum number of matching visual features used to accept the same camera angle.

Min Frames
Groups smaller than this are skipped during trail and timelapse export.

Feature Side
Working resolution for grouping analysis. Larger values can improve matching but use more memory.

Time Window Hours
Photos taken within this many hours are more likely to stay in the same group when Time Metadata is enabled.

Output Max Side
Limits the longest edge of trail images. Enable Keep Original Size to export at source dimensions without output resizing.

Image Format / JPEG Quality
PNG is lossless and larger. JPEG is smaller; higher JPEG quality preserves more faint detail.

Video Format / Video Max Side / FPS
MP4 is broadly compatible. WebM uses VP9 when the installed OpenCV build supports it. FPS controls playback speed; Video Max Side limits resolution. Enable Keep Original Video Size to make the timelapse at the source photo dimensions without video resizing.

Manual Review
Analyze Groups first. You can rename, add, drag-reorder, move or remove photos, select cards with Ctrl/Command or Shift, drag selected photo cards onto another group, navigate with arrow keys, and undo up to 50 edits. Export Edited writes only non-empty groups.

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
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass
