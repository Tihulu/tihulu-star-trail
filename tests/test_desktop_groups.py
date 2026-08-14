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


def test_workspace_reorders_selected_photos_as_a_block_and_undoes() -> None:
    group = EditableGroup(
        "group_001",
        [assigned_photo(Path(name)) for name in ("one.jpg", "two.jpg", "three.jpg", "four.jpg")],
    )
    workspace = GroupWorkspace([group])

    selected = workspace.reorder_photos(0, [1, 2], 0)

    assert selected == [0, 1]
    assert [photo.path.name for photo in workspace.groups[0].photos] == [
        "two.jpg", "three.jpg", "one.jpg", "four.jpg"
    ]
    assert workspace.undo()
    assert [photo.path.name for photo in workspace.groups[0].photos] == [
        "one.jpg", "two.jpg", "three.jpg", "four.jpg"
    ]


def test_workspace_can_apply_name_order_for_timelapse() -> None:
    group = EditableGroup(
        "group_001",
        [assigned_photo(Path(name)) for name in ("IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg")],
    )
    workspace = GroupWorkspace([group])

    workspace.sort_photos(0, "name")

    assert [photo.path.name for photo in workspace.groups[0].photos] == [
        "IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"
    ]
    assert workspace.undo()
    assert [photo.path.name for photo in workspace.groups[0].photos] == [
        "IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"
    ]


def test_workspace_can_reverse_the_explicit_timelapse_order() -> None:
    group = EditableGroup(
        "group_001",
        [assigned_photo(Path(name)) for name in ("IMG_2.jpg", "IMG_10.jpg", "IMG_1.jpg")],
    )
    workspace = GroupWorkspace([group])

    workspace.sort_photos(0, "name", reverse=True)

    assert [photo.path.name for photo in workspace.groups[0].photos] == [
        "IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"
    ]


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
    received_max_sides: list[object] = []
    preserves_order: list[bool] = []

    def fake_timelapses(groups, output, **kwargs):
        seen.append([group.name for group in groups])
        received_max_sides.append(kwargs["max_side"])
        preserves_order.append(kwargs["preserve_order"])
        return [output / "chosen_timelapse.mp4"]

    monkeypatch.setattr(engine, "render_group_timelapses", fake_timelapses)
    result = engine.render_selected_group(
        selected,
        {"output": str(tmp_path / "output"), "video_max_side": 0},
        trail=False,
        timelapse=True,
    )

    assert seen == [[selected.name]]
    assert received_max_sides == [None]
    assert preserves_order == [True]
    assert result["timelapses"] == [str(tmp_path / "output" / "timelapses" / "chosen_timelapse.mp4")]
