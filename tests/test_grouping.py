from pathlib import Path

import cv2
import numpy as np

from tihulu_star_trail.grouping import build_angle_groups, extract_signature, score_signatures
from tihulu_star_trail.images import write_bgr


def test_grouping_keeps_same_viewpoint_and_splits_different_scenes(tmp_path: Path) -> None:
    first = tmp_path / "001_same.png"
    second = tmp_path / "002_same_brighter.png"
    different = tmp_path / "003_different_color_angle.png"
    same_scene = _same_viewpoint_scene()
    write_bgr(first, same_scene)
    brighter_scene = np.clip(same_scene.astype(np.int16) + 20, 0, 255).astype(np.uint8)
    write_bgr(second, brighter_scene)
    write_bgr(different, _different_viewpoint_scene())

    same_score = score_signatures(
        extract_signature(first, max_side=320),
        extract_signature(second, max_side=320),
    )
    different_score = score_signatures(
        extract_signature(first, max_side=320),
        extract_signature(different, max_side=320),
    )
    groups = build_angle_groups([first, second, different], max_side=320)

    assert same_score.score > 0.7
    assert different_score.score < 0.2
    assert [[photo.path.name for photo in group.photos] for group in groups] == [
        ["001_same.png", "002_same_brighter.png"],
        ["003_different_color_angle.png"],
    ]


def _same_viewpoint_scene() -> np.ndarray:
    rng = np.random.default_rng(23)
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[:] = (12, 8, 16)
    for _ in range(90):
        x = int(rng.integers(10, 310))
        y = int(rng.integers(10, 150))
        color = int(rng.integers(120, 255))
        cv2.circle(image, (x, y), int(rng.integers(1, 3)), (color, color, color), -1)
    horizon = np.array(
        [
            [0, 190],
            [50, 175],
            [95, 188],
            [145, 162],
            [190, 185],
            [240, 168],
            [320, 190],
            [320, 240],
            [0, 240],
        ],
        np.int32,
    )
    cv2.fillPoly(image, [horizon], (8, 10, 12))
    cv2.rectangle(image, (45, 145), (100, 210), (34, 38, 42), -1)
    cv2.line(image, (45, 145), (100, 210), (180, 180, 180), 2)
    cv2.line(image, (100, 145), (45, 210), (120, 120, 120), 2)
    cv2.circle(image, (230, 165), 16, (100, 80, 65), -1)
    return image


def _different_viewpoint_scene() -> np.ndarray:
    rng = np.random.default_rng(444)
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[:] = (70, 18, 12)
    for _ in range(90):
        x = int(rng.integers(10, 310))
        y = int(rng.integers(10, 150))
        color = int(rng.integers(80, 240))
        cv2.circle(
            image,
            (x, y),
            int(rng.integers(1, 3)),
            (color // 3, color, color // 2),
            -1,
        )
    horizon = np.array(
        [
            [0, 165],
            [40, 150],
            [90, 170],
            [130, 140],
            [180, 175],
            [220, 155],
            [320, 165],
            [320, 240],
            [0, 240],
        ],
        np.int32,
    )
    cv2.fillPoly(image, [horizon], (40, 10, 8))
    cv2.rectangle(image, (205, 95), (285, 225), (80, 18, 20), -1)
    cv2.line(image, (205, 95), (285, 225), (0, 200, 255), 3)
    cv2.line(image, (285, 95), (205, 225), (0, 160, 255), 3)
    cv2.circle(image, (70, 145), 20, (0, 255, 210), -1)
    return image
