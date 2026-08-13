from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:
    from .grouping import AngleGroup
from .images import list_images, read_bgr, sort_images_by_time, write_bgr

Progress = Callable[[str], None]


def stack_lighten(
    paths: Iterable[Path],
    output_path: Path,
    jpeg_quality: int = 95,
    resize_to_first: bool = True,
    progress: Progress | None = None,
) -> Path:
    import cv2
    import numpy as np

    ordered_paths = sort_images_by_time(list(paths))
    if not ordered_paths:
        raise ValueError("No images were provided for stacking.")

    first = read_bgr(ordered_paths[0])
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


def render_group_trails(
    groups: list[AngleGroup],
    output_dir: Path,
    min_frames: int = 2,
    jpeg_quality: int = 95,
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
        output_path = output_dir / f"{group.name}_star_trail.jpg"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(group.photos)} frames")
        rendered.append(
            stack_lighten(
                [photo.path for photo in group.photos],
                output_path,
                jpeg_quality=jpeg_quality,
                progress=progress,
            )
        )
    return rendered


def render_trails_from_group_dirs(
    input_dir: Path,
    output_dir: Path,
    min_frames: int = 2,
    jpeg_quality: int = 95,
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
        output_path = output_dir / f"{group_dir.name}_star_trail.jpg"
        if progress is not None:
            progress(f"Rendering {output_path.name} from {len(images)} frames")
        rendered.append(
            stack_lighten(
                images,
                output_path,
                jpeg_quality=jpeg_quality,
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

