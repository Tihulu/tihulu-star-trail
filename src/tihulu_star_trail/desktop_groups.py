from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .grouping import AngleGroup, AssignedPhoto


@dataclass
class EditableGroup:
    name: str
    photos: list[AssignedPhoto] = field(default_factory=list)

    @property
    def match_scores(self) -> list[float]:
        return [photo.score for photo in self.photos if photo.matched_against != "new-group"]


class GroupWorkspace:
    """Mutable, undoable desktop representation of detected photo groups."""

    def __init__(self, groups: Iterable[EditableGroup] = ()) -> None:
        self.groups = [self._copy_group(group) for group in groups]
        self._undo: list[list[EditableGroup]] = []

    @classmethod
    def from_angle_groups(cls, groups: Iterable[AngleGroup]) -> GroupWorkspace:
        return cls(EditableGroup(group.name, list(group.photos)) for group in groups)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    def snapshot(self) -> None:
        self._undo.append([self._copy_group(group) for group in self.groups])
        if len(self._undo) > 50:
            self._undo.pop(0)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self.groups = self._undo.pop()
        return True

    def add_group(self, name: str | None = None) -> int:
        self.snapshot()
        resolved = self.unique_name(name or f"group_{len(self.groups) + 1:03d}")
        self.groups.append(EditableGroup(resolved))
        return len(self.groups) - 1

    def rename_group(self, index: int, name: str) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Group name cannot be empty.")
        self.snapshot()
        self.groups[index].name = self.unique_name(cleaned, exclude=index)

    def reorder_group(self, index: int, offset: int) -> int:
        target = max(0, min(index + offset, len(self.groups) - 1))
        if target == index:
            return index
        self.snapshot()
        group = self.groups.pop(index)
        self.groups.insert(target, group)
        return target

    def move_photos(self, source: int, photo_indices: Iterable[int], target: int) -> None:
        selected = sorted(set(photo_indices))
        if not selected or source == target:
            return
        self.snapshot()
        source_photos = self.groups[source].photos
        moving = [source_photos[index] for index in selected]
        selected_set = set(selected)
        self.groups[source].photos = [
            photo for index, photo in enumerate(source_photos) if index not in selected_set
        ]
        self.groups[target].photos.extend(moving)

    def remove_photos(self, group_index: int, photo_indices: Iterable[int]) -> None:
        selected = set(photo_indices)
        if not selected:
            return
        self.snapshot()
        self.groups[group_index].photos = [
            photo
            for index, photo in enumerate(self.groups[group_index].photos)
            if index not in selected
        ]

    def nonempty_groups(self) -> list[EditableGroup]:
        return [self._copy_group(group) for group in self.groups if group.photos]

    def unique_name(self, requested: str, exclude: int | None = None) -> str:
        safe = _safe_group_name(requested)
        existing = {
            group.name.casefold()
            for index, group in enumerate(self.groups)
            if index != exclude
        }
        if safe.casefold() not in existing:
            return safe
        suffix = 2
        while f"{safe}_{suffix}".casefold() in existing:
            suffix += 1
        return f"{safe}_{suffix}"

    @staticmethod
    def _copy_group(group: EditableGroup) -> EditableGroup:
        return EditableGroup(group.name, list(group.photos))


def assigned_photo(path: Path) -> AssignedPhoto:
    return AssignedPhoto(
        path=Path(path),
        captured_at=None,
        score=1.0,
        matched_against="manual",
    )


def _safe_group_name(name: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in name.strip()
    ).strip("_")
    return safe or "group"
