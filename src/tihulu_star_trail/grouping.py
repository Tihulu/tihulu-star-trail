from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .images import read_capture_time, read_gray, sort_images_by_time

Progress = Callable[[str], None]


@dataclass(frozen=True)
class ImageSignature:
    path: Path
    points: np.ndarray
    descriptors: np.ndarray | None
    width: int
    height: int


@dataclass(frozen=True)
class MatchScore:
    score: float
    good_matches: int
    inliers: int
    inlier_ratio: float


@dataclass(frozen=True)
class AssignedPhoto:
    path: Path
    captured_at: datetime | None
    score: float
    matched_against: str


@dataclass
class AngleGroup:
    photos: list[AssignedPhoto]
    representative: ImageSignature
    last_signature: ImageSignature
    match_scores: list[float] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"group_{self.index:03d}"

    index: int = 0


def extract_signature(
    path: Path,
    max_side: int = 1000,
    nfeatures: int = 2500,
) -> ImageSignature:
    gray = read_gray(path)
    height, width = gray.shape[:2]
    longest = max(width, height)
    if longest > max_side:
        scale = max_side / float(longest)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)

    gray = _prepare_for_features(gray)
    orb = cv2.ORB_create(nfeatures=nfeatures, fastThreshold=7)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if not keypoints:
        points = np.empty((0, 2), dtype=np.float32)
    else:
        points = np.float32([keypoint.pt for keypoint in keypoints])

    return ImageSignature(
        path=path,
        points=points,
        descriptors=descriptors,
        width=width,
        height=height,
    )


def score_signatures(
    first: ImageSignature,
    second: ImageSignature,
    min_matches: int = 18,
    ratio: float = 0.75,
) -> MatchScore:
    if first.descriptors is None or second.descriptors is None:
        return MatchScore(0.0, 0, 0, 0.0)
    if len(first.descriptors) < 2 or len(second.descriptors) < 2:
        return MatchScore(0.0, 0, 0, 0.0)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw_matches = matcher.knnMatch(first.descriptors, second.descriptors, k=2)
    good_matches = [
        match
        for pair in raw_matches
        if len(pair) == 2
        for match, neighbor in [pair]
        if match.distance < ratio * neighbor.distance
    ]

    if len(good_matches) < 4:
        score = min(len(good_matches) / float(max(min_matches, 1)), 1.0) * 0.1
        return MatchScore(score, len(good_matches), 0, 0.0)

    source_points = np.float32(
        [first.points[match.queryIdx] for match in good_matches]
    ).reshape(-1, 1, 2)
    target_points = np.float32(
        [second.points[match.trainIdx] for match in good_matches]
    ).reshape(-1, 1, 2)

    _homography, mask = cv2.findHomography(
        source_points,
        target_points,
        cv2.RANSAC,
        5.0,
    )
    if mask is None:
        return MatchScore(0.0, len(good_matches), 0, 0.0)

    inliers = int(mask.sum())
    inlier_ratio = inliers / float(max(len(good_matches), 1))
    inlier_target = max(min_matches * 3, 1)
    inlier_coverage = min(inliers / float(inlier_target), 1.0)
    feature_base = max(min(len(first.points), len(second.points)), 1)
    match_density = min(len(good_matches) / float(feature_base) * 3.0, 1.0)

    score = (0.55 * inlier_ratio) + (0.35 * inlier_coverage) + (0.10 * match_density)
    if inliers < min_matches:
        score *= inliers / float(max(min_matches, 1))

    return MatchScore(
        score=max(0.0, min(score, 1.0)),
        good_matches=len(good_matches),
        inliers=inliers,
        inlier_ratio=inlier_ratio,
    )


def build_angle_groups(
    paths: list[Path],
    threshold: float = 0.32,
    min_matches: int = 18,
    max_side: int = 1000,
    nfeatures: int = 2500,
    progress: Progress | None = None,
) -> list[AngleGroup]:
    ordered_paths = sort_images_by_time(paths)
    groups: list[AngleGroup] = []
    total = len(ordered_paths)

    for index, path in enumerate(ordered_paths, start=1):
        if progress is not None:
            progress(f"[{index}/{total}] analyzing {path.name}")

        signature = extract_signature(path, max_side=max_side, nfeatures=nfeatures)
        captured_at = read_capture_time(path)

        if not groups:
            groups.append(_new_group(signature, captured_at))
            continue

        best_group: AngleGroup | None = None
        best_score = MatchScore(0.0, 0, 0, 0.0)
        best_label = "none"

        for group in groups:
            representative_score = score_signatures(
                group.representative,
                signature,
                min_matches=min_matches,
            )
            last_score = score_signatures(
                group.last_signature,
                signature,
                min_matches=min_matches,
            )
            candidate_score = (
                representative_score
                if representative_score.score >= last_score.score
                else last_score
            )
            candidate_label = "representative" if candidate_score is representative_score else "latest"
            if candidate_score.score > best_score.score:
                best_group = group
                best_score = candidate_score
                best_label = candidate_label

        if best_group is None or best_score.score < threshold:
            groups.append(_new_group(signature, captured_at))
            continue

        best_group.photos.append(
            AssignedPhoto(
                path=path,
                captured_at=captured_at,
                score=best_score.score,
                matched_against=best_label,
            )
        )
        best_group.match_scores.append(best_score.score)
        best_group.last_signature = signature

    for group_index, group in enumerate(groups, start=1):
        group.index = group_index
    return groups


def _new_group(signature: ImageSignature, captured_at: datetime | None) -> AngleGroup:
    return AngleGroup(
        photos=[
            AssignedPhoto(
                path=signature.path,
                captured_at=captured_at,
                score=1.0,
                matched_against="new-group",
            )
        ],
        representative=signature,
        last_signature=signature,
    )


def _prepare_for_features(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)

