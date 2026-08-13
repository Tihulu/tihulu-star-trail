from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .defaults import (
    DEFAULT_GROUPING_THRESHOLD,
    DEFAULT_MAX_SIDE,
    DEFAULT_MIN_MATCHES,
    DEFAULT_NFEATURES,
    DEFAULT_TIME_METADATA,
    DEFAULT_TIME_WINDOW_MINUTES,
)
from .images import read_capture_time, read_gray, sort_images_by_time

Progress = Callable[[str], None]

MIN_INLIER_RATIO = 0.38
MIN_POINT_SPREAD = 0.12
MIN_GEOMETRY_QUALITY = 0.25


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
    point_spread: float = 0.0
    geometry_quality: float = 0.0


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
    representative_time: datetime | None = None
    last_time: datetime | None = None
    match_scores: list[float] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"group_{self.index:03d}"

    index: int = 0


def extract_signature(
    path: Path,
    max_side: int = DEFAULT_MAX_SIDE,
    nfeatures: int = DEFAULT_NFEATURES,
) -> ImageSignature:
    gray = read_gray(path)
    height, width = gray.shape[:2]
    longest = max(width, height)
    if longest > max_side:
        scale = max_side / float(longest)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)
        height, width = gray.shape[:2]

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
    min_matches: int = DEFAULT_MIN_MATCHES,
    ratio: float = 0.75,
) -> MatchScore:
    if first.descriptors is None or second.descriptors is None:
        return MatchScore(0.0, 0, 0, 0.0)
    if len(first.descriptors) < 2 or len(second.descriptors) < 2:
        return MatchScore(0.0, 0, 0, 0.0)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    good_matches = _mutual_ratio_matches(
        matcher,
        first.descriptors,
        second.descriptors,
        ratio,
    )

    if len(good_matches) < 4:
        score = min(len(good_matches) / float(max(min_matches, 1)), 1.0) * 0.05
        return MatchScore(score, len(good_matches), 0, 0.0)

    source_points = np.float32(
        [first.points[match.queryIdx] for match in good_matches]
    ).reshape(-1, 1, 2)
    target_points = np.float32(
        [second.points[match.trainIdx] for match in good_matches]
    ).reshape(-1, 1, 2)

    homography, mask = cv2.findHomography(
        source_points,
        target_points,
        cv2.RANSAC,
        5.0,
    )
    if mask is None or homography is None:
        return MatchScore(0.0, len(good_matches), 0, 0.0)

    inlier_mask = mask.ravel().astype(bool)
    inliers = int(inlier_mask.sum())
    inlier_ratio = inliers / float(max(len(good_matches), 1))
    source_inliers = source_points.reshape(-1, 2)[inlier_mask]
    target_inliers = target_points.reshape(-1, 2)[inlier_mask]
    point_spread = min(
        _point_spread(source_inliers, first.width, first.height),
        _point_spread(target_inliers, second.width, second.height),
    )
    geometry_quality = _homography_quality(homography, first, second)
    inlier_target = max(min_matches * 2, 1)
    inlier_coverage = min(inliers / float(inlier_target), 1.0)

    score = (
        (0.40 * inlier_ratio)
        + (0.30 * inlier_coverage)
        + (0.20 * point_spread)
        + (0.10 * geometry_quality)
    )
    if len(good_matches) < min_matches:
        score *= len(good_matches) / float(max(min_matches, 1))
    if inliers < min_matches:
        score *= (inliers / float(max(min_matches, 1))) ** 2
    score = _soft_gate(score, inlier_ratio, MIN_INLIER_RATIO)
    score = _soft_gate(score, point_spread, MIN_POINT_SPREAD)
    score = _soft_gate(score, geometry_quality, MIN_GEOMETRY_QUALITY)

    return MatchScore(
        score=max(0.0, min(score, 1.0)),
        good_matches=len(good_matches),
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        point_spread=point_spread,
        geometry_quality=geometry_quality,
    )


def build_angle_groups(
    paths: list[Path],
    threshold: float = DEFAULT_GROUPING_THRESHOLD,
    min_matches: int = DEFAULT_MIN_MATCHES,
    max_side: int = DEFAULT_MAX_SIDE,
    nfeatures: int = DEFAULT_NFEATURES,
    time_metadata: bool = DEFAULT_TIME_METADATA,
    time_window_minutes: float = DEFAULT_TIME_WINDOW_MINUTES,
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
        metadata_time = _metadata_time(path, captured_at)

        if not groups:
            groups.append(_new_group(signature, captured_at, metadata_time))
            continue

        best_group: AngleGroup | None = None
        best_score = MatchScore(0.0, 0, 0, 0.0)
        best_label = "none"

        for group in groups:
            representative_allowed = _time_allows(
                group.representative_time,
                metadata_time,
                time_metadata,
                time_window_minutes,
            )
            last_allowed = _time_allows(
                group.last_time,
                metadata_time,
                time_metadata,
                time_window_minutes,
            )
            if not representative_allowed and not last_allowed:
                continue

            representative_score = (
                score_signatures(
                    group.representative,
                    signature,
                    min_matches=min_matches,
                )
                if representative_allowed
                else MatchScore(0.0, 0, 0, 0.0)
            )
            last_score = (
                score_signatures(
                    group.last_signature,
                    signature,
                    min_matches=min_matches,
                )
                if last_allowed
                else MatchScore(0.0, 0, 0, 0.0)
            )
            candidate_score = representative_score
            candidate_label = "representative"
            if (
                last_score.score > representative_score.score
                and (
                    representative_score.score >= threshold * 0.72
                    or not representative_allowed
                )
            ):
                candidate_score = last_score
                candidate_label = "latest"
            if candidate_score.score > best_score.score:
                best_group = group
                best_score = candidate_score
                best_label = candidate_label

        if best_group is None or best_score.score < threshold:
            groups.append(_new_group(signature, captured_at, metadata_time))
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
        best_group.last_time = metadata_time

    for group_index, group in enumerate(groups, start=1):
        group.index = group_index
    return groups


def _new_group(
    signature: ImageSignature,
    captured_at: datetime | None,
    metadata_time: datetime | None,
) -> AngleGroup:
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
        representative_time=metadata_time,
        last_time=metadata_time,
    )


def _metadata_time(path: Path, captured_at: datetime | None) -> datetime | None:
    if captured_at is not None:
        return captured_at
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def _time_allows(
    first: datetime | None,
    second: datetime | None,
    enabled: bool,
    window_minutes: float,
) -> bool:
    if not enabled or first is None or second is None:
        return True
    window_seconds = max(float(window_minutes), 0.0) * 60.0
    return abs((first - second).total_seconds()) <= window_seconds


def _mutual_ratio_matches(
    matcher: cv2.BFMatcher,
    first_descriptors: np.ndarray,
    second_descriptors: np.ndarray,
    ratio: float,
) -> list[cv2.DMatch]:
    forward = _ratio_matches(matcher, first_descriptors, second_descriptors, ratio)
    reverse = _ratio_matches(matcher, second_descriptors, first_descriptors, ratio)
    reverse_pairs = {(match.trainIdx, match.queryIdx) for match in reverse}
    return [
        match
        for match in forward
        if (match.queryIdx, match.trainIdx) in reverse_pairs
    ]


def _ratio_matches(
    matcher: cv2.BFMatcher,
    query_descriptors: np.ndarray,
    train_descriptors: np.ndarray,
    ratio: float,
) -> list[cv2.DMatch]:
    raw_matches = matcher.knnMatch(query_descriptors, train_descriptors, k=2)
    return [
        match
        for pair in raw_matches
        if len(pair) == 2
        for match, neighbor in [pair]
        if match.distance < ratio * neighbor.distance
    ]


def _point_spread(points: np.ndarray, width: int, height: int) -> float:
    if len(points) < 2:
        return 0.0
    min_x, min_y = points.min(axis=0)
    max_x, max_y = points.max(axis=0)
    span_x = max(0.0, float(max_x - min_x) / float(max(width, 1)))
    span_y = max(0.0, float(max_y - min_y) / float(max(height, 1)))
    diagonal = min(
        ((span_x * span_x) + (span_y * span_y)) ** 0.5 / (2.0 ** 0.5),
        1.0,
    )
    area = min(max(span_x * span_y, 0.0) ** 0.5, 1.0)
    return max(0.0, min((0.70 * diagonal) + (0.30 * area), 1.0))


def _homography_quality(
    homography: np.ndarray,
    first: ImageSignature,
    second: ImageSignature,
) -> float:
    corners = np.float32(
        [
            [0.0, 0.0],
            [float(max(first.width - 1, 1)), 0.0],
            [float(max(first.width - 1, 1)), float(max(first.height - 1, 1))],
            [0.0, float(max(first.height - 1, 1))],
        ]
    ).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, homography).reshape(-1, 2)
    if not np.isfinite(projected).all():
        return 0.0

    projected_area = _polygon_area(projected)
    source_area = float(max(first.width * first.height, 1))
    if projected_area <= 1.0:
        return 0.0

    scale = projected_area / source_area
    scale_score = 1.0 - min(abs(float(np.log2(max(scale, 1e-6)))) / 3.0, 1.0)
    min_x, min_y = projected.min(axis=0)
    max_x, max_y = projected.max(axis=0)
    bbox_area = max(float(max_x - min_x), 0.0) * max(float(max_y - min_y), 0.0)
    target_area = float(max(second.width * second.height, 1))
    overlap_width = max(
        0.0,
        min(float(max_x), float(second.width)) - max(float(min_x), 0.0),
    )
    overlap_height = max(
        0.0,
        min(float(max_y), float(second.height)) - max(float(min_y), 0.0),
    )
    overlap = (overlap_width * overlap_height) / max(min(bbox_area, target_area), 1.0)
    overlap_score = min(max(overlap, 0.0) * 1.35, 1.0)
    return max(0.0, min((0.65 * scale_score) + (0.35 * overlap_score), 1.0))


def _polygon_area(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return abs(
        float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) * 0.5
    )


def _soft_gate(score: float, value: float, minimum: float) -> float:
    if value >= minimum:
        return score
    return score * max(value, 0.0) / max(minimum, 1e-6)


def _prepare_for_features(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)
