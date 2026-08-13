from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .defaults import (
    DEFAULT_GROUPING_THRESHOLD,
    DEFAULT_TIME_METADATA,
    DEFAULT_TIME_WINDOW_MINUTES,
)

if TYPE_CHECKING:
    from .grouping import AngleGroup

LinkMode = Literal["symlink", "copy", "hardlink", "none"]


def materialize_groups(
    groups: list[AngleGroup],
    output_dir: Path,
    link_mode: LinkMode = "symlink",
    threshold: float = DEFAULT_GROUPING_THRESHOLD,
    time_metadata: bool = DEFAULT_TIME_METADATA,
    time_window_minutes: float = DEFAULT_TIME_WINDOW_MINUTES,
) -> Path:
    output_dir = Path(output_dir)
    groups_dir = output_dir / "groups"
    groups_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": 1,
        "threshold": threshold,
        "time_metadata": time_metadata,
        "time_window_hours": round(time_window_minutes / 60.0, 4),
        "time_window_minutes": time_window_minutes,
        "link_mode": link_mode,
        "group_count": len(groups),
        "groups": [],
    }

    for group in groups:
        group_dir = groups_dir / group.name
        group_dir.mkdir(parents=True, exist_ok=True)
        group_files = []

        for photo_index, photo in enumerate(group.photos, start=1):
            destination = group_dir / f"{photo_index:04d}_{_safe_name(photo.path.name)}"
            if link_mode != "none":
                _place_photo(photo.path, destination, link_mode)

            group_files.append(
                {
                    "source": str(photo.path.resolve()),
                    "group_path": str(destination.relative_to(output_dir)),
                    "captured_at": (
                        photo.captured_at.isoformat() if photo.captured_at else None
                    ),
                    "score": round(photo.score, 4),
                    "matched_against": photo.matched_against,
                }
            )

        group_manifest = {
            "name": group.name,
            "count": len(group.photos),
            "average_score": _average(group.match_scores),
            "files": group_files,
        }
        _write_json(group_dir / "group.json", group_manifest)
        manifest["groups"].append(group_manifest)

    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _place_photo(source: Path, destination: Path, link_mode: LinkMode) -> None:
    if destination.exists() or destination.is_symlink():
        destination.unlink()

    if link_mode == "symlink":
        destination.symlink_to(source.resolve())
    elif link_mode == "copy":
        shutil.copy2(source, destination)
    elif link_mode == "hardlink":
        os.link(source, destination)
    else:
        raise ValueError(f"Unsupported link mode: {link_mode}")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_name(name: str) -> str:
    allowed = []
    for character in name:
        if character.isalnum() or character in {".", "-", "_"}:
            allowed.append(character)
        else:
            allowed.append("_")
    return "".join(allowed)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)

