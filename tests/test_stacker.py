from pathlib import Path

import numpy as np

from tihulu_star_trail.images import read_bgr, write_bgr
from tihulu_star_trail.stacker import stack_lighten


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

