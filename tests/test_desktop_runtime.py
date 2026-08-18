from tihulu_star_trail.desktop_runtime import _fit_video_size, _fps_matches


def test_video_preview_fit_preserves_aspect_ratio_without_upscaling() -> None:
    assert _fit_video_size(3840, 2160, 860, 540) == (860, 484)
    assert _fit_video_size(640, 480, 860, 540) == (640, 480)


def test_video_preview_fit_handles_invalid_dimensions() -> None:
    assert _fit_video_size(0, 1080, 860, 540) == (1, 1)


def test_fps_match_requires_exact_numeric_value() -> None:
    assert _fps_matches("31")
    assert _fps_matches(31.0)
    assert not _fps_matches("30")
    assert not _fps_matches("not-a-number")
