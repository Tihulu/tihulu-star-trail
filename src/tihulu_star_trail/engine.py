from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .grouping import build_angle_groups
from .images import list_images
from .organizer import materialize_groups
from .stacker import (
    discover_group_dirs,
    render_group_timelapses,
    render_group_trails,
    render_timelapse,
    render_timelapses_from_group_dirs,
    render_trails_from_group_dirs,
    stack_lighten,
)

Progress = Callable[[str], None]


def scan_images(payload: dict[str, Any]) -> dict[str, Any]:
    input_path = _payload_path(payload, "input")
    recursive = bool(payload.get("recursive", True))
    images = list_images(input_path, recursive=recursive)
    counts: dict[str, int] = {}
    for image in images:
        suffix = image.suffix.lower() or "none"
        counts[suffix] = counts.get(suffix, 0) + 1
    return {"count": len(images), "extensions": counts}


def execute_action(payload: dict[str, Any], progress: Progress | None = None) -> dict[str, Any]:
    action = str(payload.get("action", "run"))
    input_path = _payload_path(payload, "input")
    output_path = _payload_path(payload, "output")
    recursive = bool(payload.get("recursive", True))
    min_frames = int(payload.get("min_frames", 2))
    jpeg_quality = int(payload.get("jpeg_quality", 95))
    threshold = float(payload.get("threshold", 0.32))
    min_matches = int(payload.get("min_matches", 18))
    max_side = int(payload.get("max_side", 1000))
    nfeatures = int(payload.get("nfeatures", 2500))
    fps = float(payload.get("fps", 24.0))
    video_max_side = _optional_max_side(int(payload.get("video_max_side", 1920)))
    codec = str(payload.get("codec", "mp4v"))
    link_mode = str(payload.get("link_mode", "symlink"))

    if action in {"run", "group"}:
        paths = list_images(input_path, recursive=recursive)
        if not paths:
            raise ValueError(f"No supported images found in {input_path}")
        if progress is not None:
            progress(f"Loaded {len(paths)} image(s)")
        groups = build_angle_groups(
            paths,
            threshold=threshold,
            min_matches=min_matches,
            max_side=max_side,
            nfeatures=nfeatures,
            progress=progress,
        )
        manifest = materialize_groups(
            groups,
            output_path,
            link_mode=link_mode,
            threshold=threshold,
        )
        result: dict[str, Any] = {
            "groups": len(groups),
            "manifest": str(manifest),
        }
        if action == "run":
            trails = render_group_trails(
                groups,
                output_path / "trails",
                min_frames=min_frames,
                jpeg_quality=jpeg_quality,
                progress=progress,
            )
            result["trails"] = [str(path) for path in trails]
            if bool(payload.get("timelapse", False)):
                videos = render_group_timelapses(
                    groups,
                    output_path / "timelapses",
                    min_frames=min_frames,
                    fps=fps,
                    codec=codec,
                    max_side=video_max_side,
                    progress=progress,
                )
                result["timelapses"] = [str(path) for path in videos]
        return result

    if action == "trail":
        if input_path.is_dir() and discover_group_dirs(input_path):
            trails = render_trails_from_group_dirs(
                input_path,
                output_path,
                min_frames=min_frames,
                jpeg_quality=jpeg_quality,
                progress=progress,
            )
            return {"trails": [str(path) for path in trails]}
        paths = list_images(input_path, recursive=recursive)
        output = output_path if output_path.suffix else output_path / "star_trail.jpg"
        trail = stack_lighten(paths, output, jpeg_quality=jpeg_quality, progress=progress)
        return {"trails": [str(trail)]}

    if action == "timelapse":
        if input_path.is_dir() and discover_group_dirs(input_path):
            videos = render_timelapses_from_group_dirs(
                input_path,
                output_path,
                min_frames=min_frames,
                fps=fps,
                codec=codec,
                max_side=video_max_side,
                progress=progress,
            )
            return {"timelapses": [str(path) for path in videos]}
        paths = list_images(input_path, recursive=recursive)
        output = output_path if output_path.suffix else output_path / "timelapse.mp4"
        video = render_timelapse(
            paths,
            output,
            fps=fps,
            codec=codec,
            max_side=video_max_side,
            progress=progress,
        )
        return {"timelapses": [str(video)]}

    raise ValueError(f"Unknown action: {action}")


def _payload_path(payload: dict[str, Any], name: str) -> Path:
    value = str(payload.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name.title()} path is required")
    return Path(value).expanduser()


def _optional_max_side(value: int) -> int | None:
    return None if value <= 0 else value
