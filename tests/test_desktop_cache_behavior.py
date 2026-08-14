from pathlib import Path

from tihulu_star_trail.desktop import TihuluDesktopApp
from tihulu_star_trail.desktop_groups import EditableGroup, GroupWorkspace, assigned_photo
from tihulu_star_trail.thumbnail_cache import LRUThumbnailCache, ThumbnailGeneration, thumbnail_key


class Preference:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value


class FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class FakeGroupList:
    def __init__(self) -> None:
        self.images = {"group-0": "image"}

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.images)

    def item(self, item: str, **options: object) -> None:
        if "image" in options:
            self.images[item] = options["image"]


def make_app() -> TihuluDesktopApp:
    app = TihuluDesktopApp.__new__(TihuluDesktopApp)
    app.thumbnail_cache = LRUThumbnailCache(max_items=128, max_bytes=40 * 1024 * 1024)
    app.thumbnail_generation = ThumbnailGeneration()
    app.thumbnail_pending = set()
    app.thumbnail_waiters = {}
    app.thumbnail_futures = set()
    app.thumbnail_images = {0: "photo-image"}
    app.photo_image_labels = [FakeWidget()]
    app.group_thumbnail_images = {"group-0": "group-image"}
    app.group_list = FakeGroupList()
    app.cache_thumbnails_in_ram = Preference(True)
    app.workspace = GroupWorkspace(
        [EditableGroup("group", [assigned_photo(Path("one.jpg")), assigned_photo(Path("two.jpg"))])]
    )
    app.selected_group = 0
    app.selected_photo_indices = {1}
    app.current_photo_index = 1
    return app


def test_disabling_photo_thumbs_clears_only_photo_cache_and_ui_references() -> None:
    app = make_app()
    photo_key = thumbnail_key("photo", Path("one.jpg"), (120, 90))
    group_key = thumbnail_key("group", Path("one.jpg"), (48, 36))
    app.thumbnail_cache.put(photo_key, "photo", 10)
    app.thumbnail_cache.put(group_key, "group", 10)

    app._clear_thumbnail_cache("photo")

    assert app.thumbnail_cache.get(photo_key) is None
    assert app.thumbnail_cache.get(group_key) == "group"
    assert app.thumbnail_images == {}
    assert app.photo_image_labels[0].options["image"] == ""
    assert app.selected_photo_indices == {1}
    assert [photo.path.name for photo in app.workspace.groups[0].photos] == ["one.jpg", "two.jpg"]


def test_disabling_group_thumbs_clears_group_cache_and_ui_references() -> None:
    app = make_app()
    group_key = thumbnail_key("group", Path("one.jpg"), (48, 36))
    app.thumbnail_cache.put(group_key, "group", 10)

    app._clear_thumbnail_cache("group")

    assert app.thumbnail_cache.get(group_key) is None
    assert app.group_thumbnail_images == {}
    assert app.group_list.images["group-0"] == ""


def test_stale_async_result_cannot_enter_cache_or_update_ui() -> None:
    app = make_app()
    stale = app.thumbnail_generation.current
    app.thumbnail_generation.advance()
    key = thumbnail_key("photo", Path("old.jpg"), (120, 90))
    token = (stale, key)
    app.thumbnail_pending.add(token)
    app.thumbnail_waiters[token] = [("photo", "0", Path("old.jpg"))]

    app._handle_thumbnail_result(
        {
            "token": token,
            "generation": stale,
            "path": Path("old.jpg"),
            "key": key,
            "image": object(),
            "error": None,
        }
    )

    assert app.thumbnail_cache.get(key) is None
    assert app.thumbnail_images == {0: "photo-image"}
