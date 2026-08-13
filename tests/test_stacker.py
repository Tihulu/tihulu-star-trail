from pathlib import Path

import numpy as np
import pytest

from tihulu_star_trail.images import read_bgr, write_bgr
from tihulu_star_trail import stacker
from tihulu_star_trail.stacker import render_timelapse, stack_lighten


def test_ffmpeg_executable_prefers_packaged_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stacker, "bundled_ffmpeg_executable", lambda: "/app/ffmpeg")
    monkeypatch.setattr(stacker.shutil, "which", lambda _: "/usr/local/bin/ffmpeg")

    assert stacker.ffmpeg_executable() == "/app/ffmpeg"


def test_ffmpeg_executable_falls_back_to_system_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stacker, "bundled_ffmpeg_executable", lambda: None)
    monkeypatch.setattr(stacker.shutil, "which", lambda _: "/usr/local/bin/ffmpeg")

    assert stacker.ffmpeg_executable() == "/usr/local/bin/ffmpeg"
    assert stacker.ffmpeg_executable(require_bundled=True) is None


def test_stack_lighten_uses_pixelwise_maximum(tmp_path: Path) -> None:
    first = np.zeros((4, 4, 3), dtype=np.uint8)
    second = np.zeros((4, 4, 3), dtype=np.uint8)
    first[1, 1] = [10, 20, 30]
    second[1, 1] = [40, 5, 80]
    second[2, 2] = [3, 200, 9]

    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    output_path = tmp_path / "trail.png"
    write_bgr(first_path, first)
    write_bgr(second_path, second)

    stack_lighten([first_path, second_path], output_path)
    result = read_bgr(output_path)

    assert result[1, 1].tolist() == [40, 20, 80]
    assert result[2, 2].tolist() == [3, 200, 9]


def test_stack_lighten_preserves_original_dimensions_without_max_side(tmp_path: Path) -> None:
    frame = np.zeros((13, 17, 3), dtype=np.uint8)
    source = tmp_path / "source.png"
    output = tmp_path / "trail.png"
    write_bgr(source, frame)

    stack_lighten([source], output, max_side=None)

    assert read_bgr(output).shape[:2] == (13, 17)


def test_render_timelapse_creates_video(tmp_path: Path) -> None:
    paths = []
    for index in range(3):
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        frame[:, :, 0] = index * 40
        path = tmp_path / f"frame_{index}.png"
        write_bgr(path, frame)
        paths.append(path)

    output_path = tmp_path / "timelapse.mp4"

    render_timelapse(paths, output_path, fps=2, max_side=16)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
