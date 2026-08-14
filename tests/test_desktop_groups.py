from pathlib import Path

from tihulu_star_trail.desktop_groups import EditableGroup, GroupWorkspace, assigned_photo
from tihulu_star_trail import engine
from tihulu_star_trail.engine import export_groups


def test_workspace_moves_renames_reorders_and_undoes() -> None:
    first = EditableGroup("group_001", [assigned_photo(Path("one.jpg"))])
    second = EditableGroup("group_002", [assigned_photo(Path("two.jpg"))])
    workspace = GroupWorkspace([first, second])

    workspace.rename_group(0, "Night Sky")
    assert workspace.groups[0].name == "Night_Sky"

    workspace.move_photos(0, [0], 1)
    assert not workspace.groups[0].photos
    assert [photo.path.name for photo in workspace.groups[1].photos] == ["two.jpg", "one.jpg"]

    workspace.undo()
    assert [photo.path.name for photo in workspace.groups[0].photos] == ["one.jpg"]

    selected = workspace.reorder_group(1, -1)
    assert selected == 0
    assert workspace.groups[0].name == "group_002"


def test_workspace_creates_unique_names_and_filters_empty_groups() -> None:
    workspace = GroupWorkspace([EditableGroup("group_001")])
    created = workspace.add_group("group 001")

    assert workspace.groups[created].name == "group_001_2"
    assert workspace.nonempty_groups() == []


def test_editable_groups_can_be_exported_to_a_manifest(tmp_path: Path) -> None:
    photo_path = tmp_path / "photo.jpg"
    photo_path.write_bytes(b"not decoded when trails are disabled")
    workspace = GroupWorkspace([
        EditableGroup("edited_group", [assigned_photo(photo_path)])
    ])

    result = export_groups(
        workspace.nonempty_groups(),
        {
            "output": str(tmp_path / "output"),
            "link_mode": "none",
            "render_trails": False,
        },
    )

    assert result["groups"] == 1
    assert Path(result["manifest"]).exists()


def test_selected_group_render_only_uses_the_chosen_group(tmp_path: Path, monkeypatch) -> None:
    selected = EditableGroup("chosen", [assigned_photo(tmp_path / "chosen.jpg")])
    other = EditableGroup("other", [assigned_photo(tmp_path / "other.jpg")])
    seen: list[list[str]] = []

    def fake_trails(groups, output, **_kwargs):
        seen.append([group.name for group in groups])
        return [output / "chosen_star_trail.jpg"]

    monkeypatch.setattr(engine, "render_group_trails", fake_trails)
    result = engine.render_selected_group(
        selected,
        {"output": str(tmp_path / "output")},
        trail=True,
        timelapse=False,
    )

    assert seen == [[selected.name]]
    assert other.name not in seen[0]
    assert result["trails"] == [str(tmp_path / "output" / "trails" / "chosen_star_trail.jpg")]


def test_selected_group_timelapse_only_uses_the_chosen_group(tmp_path: Path, monkeypatch) -> None:
    selected = EditableGroup("chosen", [assigned_photo(tmp_path / "chosen.jpg")])
    seen: list[list[str]] = []

    def fake_timelapses(groups, output, **_kwargs):
        seen.append([group.name for group in groups])
        return [output / "chosen_timelapse.mp4"]

    monkeypatch.setattr(engine, "render_group_timelapses", fake_timelapses)
    result = engine.render_selected_group(
        selected,
        {"output": str(tmp_path / "output")},
        trail=False,
        timelapse=True,
    )

    assert seen == [[selected.name]]
    assert result["timelapses"] == [str(tmp_path / "output" / "timelapses" / "chosen_timelapse.mp4")]
