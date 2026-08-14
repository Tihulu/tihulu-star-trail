from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .defaults import (
    DEFAULT_GROUPING_THRESHOLD,
    DEFAULT_MAX_SIDE,
    DEFAULT_MIN_MATCHES,
    DEFAULT_NFEATURES,
    DEFAULT_TIME_METADATA,
    DEFAULT_TIME_WINDOW_MINUTES,
)
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


def analyze_groups(
    payload: dict[str, Any], progress: Progress | None = None
) -> list[Any]:
    input_path = _payload_path(payload, "input")
    paths = list_images(input_path, recursive=bool(payload.get("recursive", True)))
    if not paths:
        raise ValueError(f"No supported images found in {input_path}")
    return build_angle_groups(
        paths,
        threshold=float(payload.get("threshold", DEFAULT_GROUPING_THRESHOLD)),
        min_matches=int(payload.get("min_matches", DEFAULT_MIN_MATCHES)),
        max_side=int(payload.get("max_side", DEFAULT_MAX_SIDE)),
        nfeatures=int(payload.get("nfeatures", DEFAULT_NFEATURES)),
        time_metadata=bool(payload.get("time_metadata", DEFAULT_TIME_METADATA)),
        time_window_minutes=_payload_time_window_minutes(payload),
        progress=progress,
    )


def export_groups(
    groups: list[Any], payload: dict[str, Any], progress: Progress | None = None
) -> dict[str, Any]:
    if not groups:
        raise ValueError("No non-empty groups are available to export.")
    output_path = _payload_path(payload, "output")
    threshold = float(payload.get("threshold", DEFAULT_GROUPING_THRESHOLD))
    time_metadata = bool(payload.get("time_metadata", DEFAULT_TIME_METADATA))
    time_window_minutes = _payload_time_window_minutes(payload)
    manifest = materialize_groups(
        groups,
        output_path,
        link_mode=str(payload.get("link_mode", "symlink")),
        threshold=threshold,
        time_metadata=time_metadata,
        time_window_minutes=time_window_minutes,
    )
    result: dict[str, Any] = {"groups": len(groups), "manifest": str(manifest)}
    if bool(payload.get("render_trails", True)):
        trails = render_group_trails(
            groups,
            output_path / "trails",
            min_frames=int(payload.get("min_frames", 2)),
            jpeg_quality=int(payload.get("jpeg_quality", 95)),
            image_format=str(payload.get("image_format", "jpeg")),
            max_side=_optional_max_side(int(payload.get("output_max_side", 0))),
            progress=progress,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
        result["trails"] = [str(path) for path in trails]
    if bool(payload.get("timelapse", False)):
        videos = render_group_timelapses(
            groups,
            output_path / "timelapses",
            min_frames=int(payload.get("min_frames", 2)),
            fps=float(payload.get("fps", 24.0)),
            codec=str(payload.get("codec", "mp4v")),
            max_side=_optional_max_side(int(payload.get("video_max_side", 1920))),
            video_format=str(payload.get("video_extension", "mp4")),
            bitrate_mbps=_optional_float(payload.get("video_quality_mbps")),
            progress=progress,
            preserve_order=True,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
        result["timelapses"] = [str(path) for path in videos]
    return result


def render_selected_group(
    group: Any,
    payload: dict[str, Any],
    *,
    trail: bool,
    timelapse: bool,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Render media for one manually selected group without exporting every group."""
    if not group.photos:
        raise ValueError("The selected group has no photos.")
    if not trail and not timelapse:
        raise ValueError("Choose a trail or timelapse export.")

    output_path = _payload_path(payload, "output")
    result: dict[str, Any] = {"groups": 1}
    if trail:
        trails = render_group_trails(
            [group],
            output_path / "trails",
            min_frames=int(payload.get("min_frames", 2)),
            jpeg_quality=int(payload.get("jpeg_quality", 95)),
            image_format=str(payload.get("image_format", "jpeg")),
            max_side=_optional_max_side(int(payload.get("output_max_side", 0))),
            progress=progress,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
        result["trails"] = [str(path) for path in trails]
    if timelapse:
        videos = render_group_timelapses(
            [group],
            output_path / "timelapses",
            min_frames=int(payload.get("min_frames", 2)),
            fps=float(payload.get("fps", 24.0)),
            codec=str(payload.get("codec", "mp4v")),
            max_side=_optional_max_side(int(payload.get("video_max_side", 1920))),
            video_format=str(payload.get("video_extension", "mp4")),
            bitrate_mbps=_optional_float(payload.get("video_quality_mbps")),
            progress=progress,
            preserve_order=True,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
        result["timelapses"] = [str(path) for path in videos]
    return result


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
    threshold = float(payload.get("threshold", DEFAULT_GROUPING_THRESHOLD))
    min_matches = int(payload.get("min_matches", DEFAULT_MIN_MATCHES))
    max_side = int(payload.get("max_side", DEFAULT_MAX_SIDE))
    nfeatures = int(payload.get("nfeatures", DEFAULT_NFEATURES))
    time_metadata = bool(payload.get("time_metadata", DEFAULT_TIME_METADATA))
    time_window_minutes = _payload_time_window_minutes(payload)
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
            if time_metadata:
                time_window_hours = time_window_minutes / 60.0
                progress(
                    f"Time metadata guard enabled ({time_window_hours:g} hour window)"
                )
        groups = build_angle_groups(
            paths,
            threshold=threshold,
            min_matches=min_matches,
            max_side=max_side,
            nfeatures=nfeatures,
            time_metadata=time_metadata,
            time_window_minutes=time_window_minutes,
            progress=progress,
        )
        manifest = materialize_groups(
            groups,
            output_path,
            link_mode=link_mode,
            threshold=threshold,
            time_metadata=time_metadata,
            time_window_minutes=time_window_minutes,
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
                image_format=str(payload.get("image_format", "jpeg")),
                max_side=_optional_max_side(int(payload.get("output_max_side", 0))),
                progress=progress,
                hardware_mode=str(payload.get("hardware_acceleration", "auto")),
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
                    video_format=str(payload.get("video_extension", "mp4")),
                    bitrate_mbps=_optional_float(payload.get("video_quality_mbps")),
                    progress=progress,
                    hardware_mode=str(payload.get("hardware_acceleration", "auto")),
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
                image_format=str(payload.get("image_format", "jpeg")),
                max_side=_optional_max_side(int(payload.get("output_max_side", 0))),
                progress=progress,
                hardware_mode=str(payload.get("hardware_acceleration", "auto")),
            )
            return {"trails": [str(path) for path in trails]}
        paths = list_images(input_path, recursive=recursive)
        image_format = str(payload.get("image_format", "jpeg"))
        extension = ".png" if image_format.lower() == "png" else ".jpg"
        filename = str(payload.get("output_name", "star_trail")).strip() or "star_trail"
        output = output_path if output_path.suffix else output_path / f"{filename}{extension}"
        trail = stack_lighten(
            paths,
            output,
            jpeg_quality=jpeg_quality,
            max_side=_optional_max_side(int(payload.get("output_max_side", 0))),
            progress=progress,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
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
                video_format=str(payload.get("video_extension", "mp4")),
                bitrate_mbps=_optional_float(payload.get("video_quality_mbps")),
                progress=progress,
                hardware_mode=str(payload.get("hardware_acceleration", "auto")),
            )
            return {"timelapses": [str(path) for path in videos]}
        paths = list_images(input_path, recursive=recursive)
        filename = str(payload.get("output_name", "timelapse")).strip() or "timelapse"
        video_extension = str(payload.get("video_extension", "mp4"))
        output = output_path if output_path.suffix else output_path / f"{filename}.{video_extension}"
        video = render_timelapse(
            paths,
            output,
            fps=fps,
            codec=codec,
            max_side=video_max_side,
            bitrate_mbps=_optional_float(payload.get("video_quality_mbps")),
            progress=progress,
            hardware_mode=str(payload.get("hardware_acceleration", "auto")),
        )
        return {"timelapses": [str(video)]}

    raise ValueError(f"Unknown action: {action}")


def _payload_time_window_minutes(payload: dict[str, Any]) -> float:
    if "time_window_hours" in payload:
        return float(payload["time_window_hours"]) * 60.0
    return float(payload.get("time_window_minutes", DEFAULT_TIME_WINDOW_MINUTES))


def _payload_path(payload: dict[str, Any], name: str) -> Path:
    value = str(payload.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name.title()} path is required")
    return Path(value).expanduser()


def _optional_max_side(value: int) -> int | None:
    return None if value <= 0 else value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return None if parsed <= 0 else parsed
