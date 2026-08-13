from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:
    from .grouping import AngleGroup
from .images import list_images, read_bgr, sort_images_by_time, write_bgr

Progress = Callable[[str], None]


def bundled_ffmpeg_executable() -> str | None:
    """Return the FFmpeg executable bundled with a frozen desktop app, if any."""
    try:
        import imageio_ffmpeg
    except ModuleNotFoundError:
        return None

    binaries_dir = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
    for candidate in sorted(binaries_dir.glob("ffmpeg-*")):
        if candidate.is_file() and candidate.stat().st_mode & 0o111:
            return str(candidate)
    return None


def ffmpeg_executable(require_bundled: bool = False) -> str | None:
    """Prefer packaged FFmpeg and fall back to a system installation."""
    bundled = bundled_ffmpeg_executable()
    if bundled is not None:
        return bundled
    if require_bundled:
        return None
    return shutil.which("ffmpeg")


def check_video_dependencies(require_bundled: bool = False) -> str:
    """Verify that the FFmpeg used for bitrate-controlled video export works."""
    executable = ffmpeg_executable(require_bundled=require_bundled)
    if executable is None:
        location = "packaged" if require_bundled else "packaged or system"
        raise RuntimeError(f"No {location} FFmpeg executable is available.")
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"FFmpeg could not start: {error}") from error
    if "libx264" not in result.stdout:
        raise RuntimeError(f"FFmpeg does not include the required libx264 encoder: {executable}")
    return executable


def stack_lighten(
    paths: Iterable[Path],
    output_path: Path,
    jpeg_quality: int = 95,
    resize_to_first: bool = True,
    max_side: int | None = None,
    progress: Progress | None = None,
) -> Path:
    import cv2
    import numpy as np

    ordered_paths = sort_images_by_time(list(paths))
    if not ordered_paths:
        raise ValueError("No images were provided for stacking.")

    first = read_bgr(ordered_paths[0])
    target_size = _image_target_size(first.shape[1], first.shape[0], max_side=max_side)
    if (first.shape[1], first.shape[0]) != target_size:
        first = cv2.resize(first, target_size, interpolation=cv2.INTER_AREA)
    base_height, base_width = first.shape[:2]
    stack = first.copy()

    for index, path in enumerate(ordered_paths[1:], start=2):
        if progress is not None:
            progress(f"[{index}/{len(ordered_paths)}] stacking {path.name}")
        image = read_bgr(path)
        if image.shape[:2] != (base_height, base_width):
            if not resize_to_first:
                raise ValueError(
                    f"Image size mismatch for {path}: "
                    f"{image.shape[1]}x{image.shape[0]} != {base_width}x{base_height}"
                )
            image = cv2.resize(
                image,
                (base_width, base_height),
                interpolation=cv2.INTER_AREA,
            )
        stack = np.maximum(stack, image)

    write_bgr(output_path, stack, jpeg_quality=jpeg_quality)
    return output_path


def render_timelapse(
    paths: Iterable[Path],
    output_path: Path,
    fps: float = 24.0,
    codec: str = "mp4v",
    max_side: int | None = 1920,
    bitrate_mbps: float | None = None,
    progress: Progress | None = None,
) -> Path:
    import cv2

    ordered_paths = sort_images_by_time(list(paths))
    if not ordered_paths:
        raise ValueError("No images were provided for timelapse rendering.")
    if fps <= 0:
        raise ValueError("FPS must be greater than zero.")
    if len(codec) != 4:
        raise ValueError("Codec must be a four-character code such as mp4v or XVID.")

    output_path = Path(output_path)
    if output_path.suffix == "":
        output_path = output_path / "timelapse.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    first = read_bgr(ordered_paths[0])
    frame_size = _target_size(first.shape[1], first.shape[0], max_side=max_side)
    ffmpeg = ffmpeg_executable()
    intermediate_path = (
        output_path.with_name(f".{output_path.stem}.recording{output_path.suffix}")
        if bitrate_mbps and bitrate_mbps > 0 and ffmpeg
        else output_path
    )
    writer = cv2.VideoWriter(
        str(intermediate_path),
        cv2.VideoWriter_fourcc(*codec),
        float(fps),
        frame_size,
    )
    if not writer.isOpened():
        raise ValueError(f"Could not open video writer for {output_path}")

    try:
        for index, path in enumerate(ordered_paths, start=1):
            if progress is not None:
                progress(f"[{index}/{len(ordered_paths)}] timelapse {path.name}")
            frame = read_bgr(path)
            if frame.shape[1] != frame_size[0] or frame.shape[0] != frame_size[1]:
                frame = cv2.resize(frame, frame_size, interpolation=cv2.INTER_AREA)
            writer.write(frame)
    finally:
        writer.release()

    if intermediate_path != output_path:
        _apply_video_bitrate(
            intermediate_path,
            output_path,
            bitrate_mbps or 8.0,
            progress,
            ffmpeg=ffmpeg,
        )

    return output_path


def render_group_trails(
    groups: list[AngleGroup],
    output_dir: Path,
    min_frames: int = 2,
    jpeg_quality: int = 95,
    image_format: str = "jpeg",
    max_side: int | None = None,
    progress: Progress | None = None,
) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []

    for group in groups:
        if len(group.photos) < min_frames:
            if progress is not None:
                progress(f"Skipping {group.name}: only {len(group.photos)} frame(s)")
            continue
        extension = ".png" if image_format.lower() == "png" else ".jpg"
        output_path = output_dir / f"{group.name}_star_trail{extension}"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(group.photos)} frames")
        rendered.append(
            stack_lighten(
                [photo.path for photo in group.photos],
                output_path,
                jpeg_quality=jpeg_quality,
                max_side=max_side,
                progress=progress,
            )
        )
    return rendered


def render_group_timelapses(
    groups: list[AngleGroup],
    output_dir: Path,
    min_frames: int = 2,
    fps: float = 24.0,
    codec: str = "mp4v",
    max_side: int | None = 1920,
    video_format: str = "mp4",
    bitrate_mbps: float | None = None,
    progress: Progress | None = None,
) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []

    for group in groups:
        if len(group.photos) < min_frames:
            if progress is not None:
                progress(f"Skipping {group.name}: only {len(group.photos)} frame(s)")
            continue
        extension = ".webm" if video_format.lower() == "webm" else ".mp4"
        output_path = output_dir / f"{group.name}_timelapse{extension}"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(group.photos)} frames")
        rendered.append(
            render_timelapse(
                [photo.path for photo in group.photos],
                output_path,
                fps=fps,
                codec=codec,
                max_side=max_side,
                bitrate_mbps=bitrate_mbps,
                progress=progress,
            )
        )
    return rendered


def render_trails_from_group_dirs(
    input_dir: Path,
    output_dir: Path,
    min_frames: int = 2,
    jpeg_quality: int = 95,
    image_format: str = "jpeg",
    max_side: int | None = None,
    progress: Progress | None = None,
) -> list[Path]:
    group_dirs = discover_group_dirs(input_dir)
    if not group_dirs:
        raise ValueError(f"No group folders were found in {input_dir}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for group_dir in group_dirs:
        images = list_images(group_dir, recursive=False)
        if len(images) < min_frames:
            if progress is not None:
                progress(f"Skipping {group_dir.name}: only {len(images)} frame(s)")
            continue
        extension = ".png" if image_format.lower() == "png" else ".jpg"
        output_path = output_dir / f"{group_dir.name}_star_trail{extension}"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(images)} frames")
        rendered.append(
            stack_lighten(
                images,
                output_path,
                jpeg_quality=jpeg_quality,
                max_side=max_side,
                progress=progress,
            )
        )
    return rendered


def render_timelapses_from_group_dirs(
    input_dir: Path,
    output_dir: Path,
    min_frames: int = 2,
    fps: float = 24.0,
    codec: str = "mp4v",
    max_side: int | None = 1920,
    video_format: str = "mp4",
    bitrate_mbps: float | None = None,
    progress: Progress | None = None,
) -> list[Path]:
    group_dirs = discover_group_dirs(input_dir)
    if not group_dirs:
        raise ValueError(f"No group folders were found in {input_dir}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for group_dir in group_dirs:
        images = list_images(group_dir, recursive=False)
        if len(images) < min_frames:
            if progress is not None:
                progress(f"Skipping {group_dir.name}: only {len(images)} frame(s)")
            continue
        extension = ".webm" if video_format.lower() == "webm" else ".mp4"
        output_path = output_dir / f"{group_dir.name}_timelapse{extension}"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(images)} frames")
        rendered.append(
            render_timelapse(
                images,
                output_path,
                fps=fps,
                codec=codec,
                max_side=max_side,
                bitrate_mbps=bitrate_mbps,
                progress=progress,
            )
        )
    return rendered


def discover_group_dirs(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    roots = []
    if (input_dir / "groups").is_dir():
        roots.append(input_dir / "groups")
    roots.append(input_dir)

    group_dirs: list[Path] = []
    for root in roots:
        group_dirs.extend(
            path
            for path in root.iterdir()
            if path.is_dir() and path.name.startswith("group_")
        )
    return sorted(set(group_dirs), key=lambda path: path.name)


def _target_size(width: int, height: int, max_side: int | None) -> tuple[int, int]:
    if max_side is None or max_side <= 0:
        target_width, target_height = width, height
    else:
        scale = min(float(max_side) / float(max(width, height)), 1.0)
        target_width = max(1, int(round(width * scale)))
        target_height = max(1, int(round(height * scale)))

    if target_width % 2:
        target_width += 1
    if target_height % 2:
        target_height += 1
    return target_width, target_height


def _image_target_size(
    width: int, height: int, max_side: int | None
) -> tuple[int, int]:
    if max_side is None or max_side <= 0:
        return width, height
    scale = min(float(max_side) / float(max(width, height)), 1.0)
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def _apply_video_bitrate(
    source: Path,
    output: Path,
    bitrate_mbps: float,
    progress: Progress | None,
    ffmpeg: str | None = None,
) -> None:
    codec = "libvpx-vp9" if output.suffix.lower() == ".webm" else "libx264"
    executable = ffmpeg or ffmpeg_executable()
    if executable is None:
        source.replace(output)
        return
    command = [
        executable,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-an",
        "-c:v",
        codec,
        "-b:v",
        f"{max(float(bitrate_mbps), 0.1):g}M",
        str(output),
    ]
    if progress is not None:
        progress(f"Applying {bitrate_mbps:g} Mbps video quality")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        if progress is not None:
            progress(f"FFmpeg bitrate pass unavailable; keeping direct recording ({error})")
        source.replace(output)
    else:
        source.unlink(missing_ok=True)
