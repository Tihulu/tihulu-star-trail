from pathlib import Path

from tihulu_star_trail.thumbnail_cache import (
    LRUThumbnailCache,
    ThumbnailGeneration,
    prune_invisible_references,
    thumbnail_key,
)
from tihulu_star_trail.desktop_groups import EditableGroup, GroupWorkspace, assigned_photo


def test_lru_cache_evicts_least_recently_used_item() -> None:
    cache = LRUThumbnailCache[str, str](max_items=2, max_bytes=100)
    cache.put("one", "1", 10)
    cache.put("two", "2", 10)
    assert cache.get("one") == "1"

    evicted = cache.put("three", "3", 10)

    assert evicted == ["two"]
    assert cache.get("two") is None
    assert cache.get("one") == "1"


def test_lru_cache_honors_byte_limit_and_cleanup_predicate() -> None:
    cache = LRUThumbnailCache[tuple[str, str, int, int], str](max_items=10, max_bytes=25)
    photo = thumbnail_key("photo", Path("one.jpg"), (120, 90))
    group = thumbnail_key("group", Path("two.jpg"), (48, 36))
    cache.put(photo, "photo", 15)
    cache.put(group, "group", 15)

    assert cache.get(photo) is None
    assert cache.get(group) == "group"
    assert cache.remove_where(lambda key: key[0] == "group") == [group]
    assert cache.stats.items == 0


def test_stale_thumbnail_generation_is_rejected() -> None:
    generation = ThumbnailGeneration()
    first = generation.current
    current = generation.advance()

    assert not generation.accepts(first)
    assert generation.accepts(current)


def test_ram_cache_off_keeps_only_visible_ui_references() -> None:
    references = {0: "first", 1: "second", 2: "third"}

    removed = prune_invisible_references(references, {1})

    assert removed == [0, 2]
    assert references == {1: "second"}


def test_cache_cleanup_does_not_change_group_order_or_undo_history() -> None:
    workspace = GroupWorkspace(
        [EditableGroup("group", [assigned_photo(Path("one.jpg")), assigned_photo(Path("two.jpg"))])]
    )
    workspace.reorder_photos(0, [1], 0)
    cache = LRUThumbnailCache[str, str](max_items=2, max_bytes=20)
    cache.put("one", "thumbnail", 10)

    cache.clear()

    assert [photo.path.name for photo in workspace.groups[0].photos] == ["two.jpg", "one.jpg"]
    assert workspace.can_undo
