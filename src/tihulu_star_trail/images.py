from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable


STANDARD_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
}

RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dcr",
    ".dng",
    ".erf",
    ".kdc",
    ".mef",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rwl",
    ".rw2",
    ".srw",
    ".x3f",
}

SUPPORTED_EXTENSIONS = STANDARD_EXTENSIONS | RAW_EXTENSIONS

EXIF_DATE_TAGS = {
    306,  # DateTime
    36867,  # DateTimeOriginal
    36868,  # DateTimeDigitized
}


def is_raw_image(path: Path) -> bool:
    return path.suffix.lower() in RAW_EXTENSIONS


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def list_images(root: Path, recursive: bool = True) -> list[Path]:
    root = Path(root).expanduser()
    if root.is_file():
        if is_supported_image(root):
            return [root]
        raise ValueError(f"Unsupported image file: {root}")

    if not root.exists():
        raise FileNotFoundError(root)

    iterator: Iterable[Path] = root.rglob("*") if recursive else root.iterdir()
    return sorted(
        (path for path in iterator if is_supported_image(path)),
        key=lambda path: str(path).casefold(),
    )


def read_capture_time(path: Path) -> datetime | None:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as image:
            exif = image.getexif()
    except (OSError, UnidentifiedImageError):
        return None

    for tag in EXIF_DATE_TAGS:
        value = exif.get(tag)
        parsed = _parse_exif_datetime(value)
        if parsed is not None:
            return parsed
    return None


def sort_images_by_time(paths: Iterable[Path]) -> list[Path]:
    def key(path: Path) -> tuple[float, str]:
        captured_at = read_capture_time(path)
        if captured_at is not None:
            return (captured_at.timestamp(), str(path).casefold())
        try:
            return (path.stat().st_mtime, str(path).casefold())
        except OSError:
            return (0, str(path).casefold())

    return sorted(paths, key=key)


def read_bgr(path: Path) -> np.ndarray:
    import cv2
    import numpy as np

    path = Path(path)
    if is_raw_image(path):
        return _read_raw_bgr(path)

    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def read_gray(path: Path) -> np.ndarray:
    import cv2

    image = read_bgr(path)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def write_bgr(path: Path, image: np.ndarray, jpeg_quality: int = 95) -> None:
    import cv2

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower() or ".jpg"
    params: list[int] = []
    if suffix in {".jpg", ".jpeg"}:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    elif suffix == ".png":
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]

    ok, encoded = cv2.imencode(suffix, image, params)
    if not ok:
        raise ValueError(f"Could not encode output image: {path}")
    encoded.tofile(str(path))


def _read_raw_bgr(path: Path) -> np.ndarray:
    import cv2

    try:
        import rawpy
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "rawpy is required for RAW files. Install with: pip install rawpy"
        ) from error

    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )
    except Exception as error:
        raise ValueError(f"Could not decode RAW image {path}: {error}") from error
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _parse_exif_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        return None
    value = value.strip()
    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None
