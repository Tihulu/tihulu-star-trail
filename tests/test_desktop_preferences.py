import json
from pathlib import Path
from types import SimpleNamespace

from tihulu_star_trail.desktop import TihuluDesktopApp


class BooleanPreference:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value


def test_thumbnail_preference_round_trips(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    app = TihuluDesktopApp.__new__(TihuluDesktopApp)
    app.preferences_path = settings
    app.show_photo_thumbnails = BooleanPreference(False)
    app.show_group_thumbnails = BooleanPreference(True)

    app._save_preferences()

    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "show_photo_thumbnails": False,
        "show_group_thumbnails": True,
    }
    assert app._load_preferences() == {
        "show_photo_thumbnails": False,
        "show_group_thumbnails": True,
    }


def test_invalid_thumbnail_preferences_fall_back_safely(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("not json", encoding="utf-8")
    app = TihuluDesktopApp.__new__(TihuluDesktopApp)
    app.preferences_path = settings

    assert app._load_preferences() == {}


def test_mouse_wheel_units_support_macos_and_linux_events() -> None:
    assert TihuluDesktopApp._wheel_units(SimpleNamespace(num=None, delta=1)) == -1
    assert TihuluDesktopApp._wheel_units(SimpleNamespace(num=None, delta=-120)) == 1
    assert TihuluDesktopApp._wheel_units(SimpleNamespace(num=4, delta=0)) == -1
    assert TihuluDesktopApp._wheel_units(SimpleNamespace(num=5, delta=0)) == 1
