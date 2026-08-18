from pathlib import Path

from tihulu_star_trail.windows_runtime import default_link_mode, windows_preferences_path


def test_windows_defaults_to_copy_output() -> None:
    assert default_link_mode("win32") == "copy"
    assert default_link_mode("darwin") == "symlink"
    assert default_link_mode("linux") == "symlink"


def test_windows_preferences_use_local_app_data() -> None:
    path = windows_preferences_path(
        environ={"LOCALAPPDATA": r"C:\Users\Tihulu\AppData\Local"},
        home=Path("C:/unused"),
    )

    assert path == Path(r"C:\Users\Tihulu\AppData\Local") / "Tihulu Star Trail" / "settings.json"


def test_windows_preferences_fall_back_to_home() -> None:
    home = Path("C:/Users/Tihulu")

    assert windows_preferences_path(environ={}, home=home) == (
        home / "AppData" / "Local" / "Tihulu Star Trail" / "settings.json"
    )
