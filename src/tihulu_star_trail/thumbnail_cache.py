from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class CacheStats:
    items: int
    bytes: int
    max_items: int
    max_bytes: int


class LRUThumbnailCache(Generic[K, V]):
    """Thread-safe, byte-aware LRU cache for downscaled images only."""

    def __init__(self, max_items: int = 128, max_bytes: int = 40 * 1024 * 1024) -> None:
        if max_items < 1 or max_bytes < 1:
            raise ValueError("Thumbnail cache limits must be positive.")
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._items: OrderedDict[K, tuple[V, int]] = OrderedDict()
        self._bytes = 0
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._items.pop(key, None)
            if entry is None:
                return None
            self._items[key] = entry
            return entry[0]

    def put(self, key: K, value: V, size_bytes: int) -> list[K]:
        if size_bytes < 0:
            raise ValueError("Thumbnail byte size cannot be negative.")
        evicted: list[K] = []
        with self._lock:
            previous = self._items.pop(key, None)
            if previous is not None:
                self._bytes -= previous[1]
            if size_bytes > self.max_bytes:
                return [key]
            self._items[key] = (value, size_bytes)
            self._bytes += size_bytes
            while len(self._items) > self.max_items or self._bytes > self.max_bytes:
                old_key, (_, old_size) = self._items.popitem(last=False)
                self._bytes -= old_size
                evicted.append(old_key)
        return evicted

    def remove_where(self, predicate: Callable[[K], bool]) -> list[K]:
        removed: list[K] = []
        with self._lock:
            for key in list(self._items):
                if predicate(key):
                    _, size = self._items.pop(key)
                    self._bytes -= size
                    removed.append(key)
        return removed

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._items

    @property
    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(len(self._items), self._bytes, self.max_items, self.max_bytes)


class ThumbnailGeneration:
    """Reject asynchronous results from an obsolete UI generation."""

    def __init__(self) -> None:
        self._value = 0

    @property
    def current(self) -> int:
        return self._value

    def advance(self) -> int:
        self._value += 1
        return self._value

    def accepts(self, generation: int) -> bool:
        return generation == self._value


def thumbnail_key(kind: str, path: Path, bounds: tuple[int, int]) -> tuple[str, str, int, int]:
    return kind, str(Path(path)), int(bounds[0]), int(bounds[1])


def estimate_image_bytes(image: object) -> int:
    width, height = getattr(image, "size", (0, 0))
    bands = len(getattr(image, "getbands", lambda: ("R", "G", "B", "A"))())
    return int(width) * int(height) * max(1, bands)


def prune_invisible_references(references: dict[K, V], visible: set[K]) -> list[K]:
    """Drop non-visible UI references when persistent RAM caching is disabled."""
    removed = [key for key in references if key not in visible]
    for key in removed:
        references.pop(key, None)
    return removed


def decode_thumbnail(path: Path, bounds: tuple[int, int]) -> object:
    """Decode a source and return only a downscaled PIL image."""
    from PIL import Image, ImageOps

    from .images import is_raw_image, read_bgr

    path = Path(path)
    if is_raw_image(path):
        import cv2

        bgr = read_bgr(path)
        height, width = bgr.shape[:2]
        scale = min(bounds[0] / width, bounds[1] / height, 1.0)
        target = (max(1, round(width * scale)), max(1, round(height * scale)))
        if target != (width, height):
            bgr = cv2.resize(bgr, target, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        # A contain-style thumbnail turns panoramic frames into an almost
        # invisible strip. Fill the fixed review-card area instead.
        return ImageOps.fit(image, bounds, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
