from __future__ import annotations

import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

_TARGET_URL = "https://www.instagram.com/world_of_31"


def _fps_matches(value: object) -> bool:
    try:
        return float(str(value).strip()) == 31.0
    except (TypeError, ValueError):
        return False


def _fit_video_size(width: int, height: int, max_width: int, max_height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return 1, 1
    scale = min(max_width / width, max_height / height, 1.0)
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def _maybe_open_link(self: Any) -> None:
    if _fps_matches(self.fps.get()):
        try:
            webbrowser.open_new_tab(_TARGET_URL)
        except Exception:
            pass


def _build_layout(self: Any) -> None:
    from .desktop import BG, LOG_BG, LOG_FG

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
    process_host = self.ttk.Frame(notebook, style="App.TFrame")
    review_tab = self.ttk.Frame(notebook, style="App.TFrame", padding=(0, 10, 0, 0))
    notebook.add(process_host, text="Process & Export")
    notebook.add(review_tab, text="Manual Review")

    process_host.columnconfigure(0, weight=1)
    process_host.rowconfigure(0, weight=1)
    process_canvas = self.tk.Canvas(
        process_host,
        bg=BG,
        highlightthickness=0,
        bd=0,
        relief="flat",
    )
    process_scrollbar = self.ttk.Scrollbar(
        process_host,
        orient="vertical",
        command=process_canvas.yview,
        style="Slim.Vertical.TScrollbar",
    )
    process_canvas.configure(yscrollcommand=process_scrollbar.set)
    process_canvas.grid(row=0, column=0, sticky="nsew")
    process_scrollbar.grid(row=0, column=1, sticky="ns")

    process_tab = self.ttk.Frame(process_canvas, style="App.TFrame", padding=(0, 10, 8, 0))
    process_window = process_canvas.create_window((0, 0), window=process_tab, anchor="nw")
    self.process_canvas = process_canvas
    self.process_scrollbar = process_scrollbar

    def sync_scrollregion(_event: Any = None) -> None:
        process_canvas.configure(scrollregion=process_canvas.bbox("all"))

    def fit_process_width(event: Any) -> None:
        process_canvas.itemconfigure(process_window, width=max(1, event.width))
        self.root.after_idle(sync_scrollregion)

    def scroll_process(event: Any) -> str:
        units = self._wheel_units(event)
        if units:
            process_canvas.yview_scroll(units, "units")
        return "break"

    process_tab.bind("<Configure>", sync_scrollregion, add="+")
    process_canvas.bind("<Configure>", fit_process_width, add="+")

    process_tab.columnconfigure(0, weight=9)
    process_tab.columnconfigure(1, weight=11)
    process_tab.rowconfigure(0, weight=1)

    controls = self._panel(process_tab, 0, 0, "Controls")
    monitor = self._panel(process_tab, 0, 1, "Monitor & Output Preview")
    controls.columnconfigure(0, weight=1)
    monitor.columnconfigure(0, weight=1)
    monitor.columnconfigure(1, weight=1)
    monitor.rowconfigure(3, weight=1)

    self._mode_row(controls, 1)
    self._path_row(controls, 2, "Input Path", self.input_path, self._browse_input)
    self._path_row(controls, 3, "Output Path", self.output_path, self._browse_output)
    self._toggle_row(controls, 4)
    self._settings_grid(controls, 5)
    self._action_row(controls, 6)

    self.ttk.Label(monitor, text="Current Job", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 10))
    self.result_label = self.ttk.Label(monitor, textvariable=self.result, style="Result.TLabel", wraplength=520, justify="left")
    self.result_label.grid(row=1, column=1, sticky="ew", pady=(4, 10))
    monitor.bind("<Configure>", lambda event: self.result_label.configure(wraplength=max(160, event.width // 2)))
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
        insertbackground="#f2fbff",
        relief="flat",
        bd=0,
        height=24,
        wrap="word",
        font=("JetBrains Mono", 10),
    )
    self.log.grid(row=3, column=0, columnspan=2, sticky="nsew")
    log_scrollbar = self.ttk.Scrollbar(monitor, orient="vertical", command=self.log.yview)
    log_scrollbar.grid(row=3, column=2, sticky="ns")
    self.log.configure(yscrollcommand=log_scrollbar.set, state="disabled")
    self._append_log("Awaiting input.")

    def bind_process_tree(widget: Any) -> None:
        if widget is self.log:
            return
        self._bind_mousewheel(widget, scroll_process)
        for child in widget.winfo_children():
            if child is not log_scrollbar:
                bind_process_tree(child)

    bind_process_tree(process_tab)
    self._bind_mousewheel(process_canvas, scroll_process)
    self._build_review_tab(review_tab)


def _show_info(self: Any) -> None:
    original = getattr(self.__class__, "_tihulu_original_show_info")
    existing = set(self.root.winfo_children())
    original(self)
    windows = [child for child in self.root.winfo_children() if child not in existing]
    if not windows:
        return
    window = windows[-1]
    text = next((child for child in window.winfo_children() if isinstance(child, self.tk.Text)), None)
    if text is None:
        return
    text.pack_forget()
    scrollbar = self.ttk.Scrollbar(
        window,
        orient="vertical",
        command=text.yview,
        style="Slim.Vertical.TScrollbar",
    )
    scrollbar.pack(side="right", fill="y", padx=(0, 16), pady=16)
    text.configure(yscrollcommand=scrollbar.set)
    text.pack(side="left", fill="both", expand=True, padx=(16, 6), pady=16)


def _open_video_player(self: Any, path: Path) -> None:
    import cv2

    self._stop_video()
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        self._show_error(f"Could not open video: {path}")
        return

    self._video_capture = capture
    self._video_playing = True
    self._video_seek_updating = False
    self._video_fps = max(float(capture.get(cv2.CAP_PROP_FPS) or 24.0), 1.0)
    self._video_next_deadline = time.perf_counter()

    window = self.tk.Toplevel(self.root)
    self._video_window = window
    window.title(f"Timelapse Player — {path.name}")
    window.geometry("900x650")
    window.minsize(560, 420)
    window.configure(bg="#05070d")
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


def _video_tick(self: Any) -> None:
    if self._video_capture is None or not self._video_playing:
        return

    import cv2
    from PIL import Image, ImageTk

    started = time.perf_counter()
    ok, frame = self._video_capture.read()
    if not ok:
        self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._video_next_deadline = started
        ok, frame = self._video_capture.read()

    if ok:
        width = max(320, self.video_frame.winfo_width() - 20)
        height = max(240, self.video_frame.winfo_height() - 20)
        if self.video_frame.winfo_width() <= 2:
            width, height = 860, 540
        frame_height, frame_width = frame.shape[:2]
        target = _fit_video_size(frame_width, frame_height, width, height)
        if target != (frame_width, frame_height):
            frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._video_image = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.video_frame.configure(image=self._video_image, text="")

        self._video_seek_updating = True
        try:
            self.video_seek.set(max(0, self._video_capture.get(cv2.CAP_PROP_POS_FRAMES) - 1))
        finally:
            self._video_seek_updating = False

    interval = 1.0 / max(float(getattr(self, "_video_fps", 24.0)), 1.0)
    deadline = float(getattr(self, "_video_next_deadline", started)) + interval
    now = time.perf_counter()
    if deadline < now - interval:
        missed = int((now - deadline) / interval)
        for _ in range(min(missed, 4)):
            if not self._video_capture.grab():
                break
        deadline += missed * interval
    self._video_next_deadline = deadline
    delay_ms = max(1, int(round(max(0.0, deadline - time.perf_counter()) * 1000)))
    self._video_after = self.root.after(delay_ms, self._video_tick)


def _toggle_video(self: Any) -> None:
    self._video_playing = not self._video_playing
    self.video_toggle.configure(text="Pause" if self._video_playing else "Play")
    if self._video_playing:
        self._video_next_deadline = time.perf_counter()
        self._video_tick()
    elif self._video_after is not None:
        try:
            self.root.after_cancel(self._video_after)
        except self.tk.TclError:
            pass
        self._video_after = None


def _restart_video(self: Any) -> None:
    if self._video_capture is None:
        return
    import cv2

    self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    self._video_next_deadline = time.perf_counter()
    if not self._video_playing:
        self._video_playing = True
        self.video_toggle.configure(text="Pause")
        self._video_tick()


def _seek_video(self: Any, value: str) -> None:
    if self._video_capture is None or getattr(self, "_video_seek_updating", False):
        return
    import cv2

    self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(float(value))))
    self._video_next_deadline = time.perf_counter()


def _wrap_action(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
        _maybe_open_link(self)
        return original(self, *args, **kwargs)

    return wrapped


def install_desktop_runtime() -> None:
    from .desktop import TihuluDesktopApp

    if getattr(TihuluDesktopApp, "_tihulu_desktop_runtime_configured", False):
        return

    TihuluDesktopApp._tihulu_original_show_info = TihuluDesktopApp.show_info
    TihuluDesktopApp._build_layout = _build_layout
    TihuluDesktopApp.show_info = _show_info
    TihuluDesktopApp._open_video_player = _open_video_player
    TihuluDesktopApp._video_tick = _video_tick
    TihuluDesktopApp._toggle_video = _toggle_video
    TihuluDesktopApp._restart_video = _restart_video
    TihuluDesktopApp._seek_video = _seek_video
    TihuluDesktopApp.analyze = _wrap_action(TihuluDesktopApp.analyze)
    TihuluDesktopApp.run = _wrap_action(TihuluDesktopApp.run)
    TihuluDesktopApp._tihulu_desktop_runtime_configured = True
