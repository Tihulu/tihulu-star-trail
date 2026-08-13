from pathlib import Path

import pytest

from tihulu_star_trail.images import list_images


def test_list_images_recursively_finds_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.txt").write_text("not an image", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.PNG").write_bytes(b"")

    names = [path.name for path in list_images(tmp_path)]

    assert names == ["a.jpg", "c.PNG"]


def test_list_images_rejects_unsupported_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        list_images(path)

