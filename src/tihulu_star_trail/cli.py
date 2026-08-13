from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .defaults import (
    DEFAULT_GROUPING_THRESHOLD,
    DEFAULT_MAX_SIDE,
    DEFAULT_MIN_MATCHES,
    DEFAULT_NFEATURES,
    DEFAULT_TIME_METADATA,
    DEFAULT_TIME_WINDOW_MINUTES,
)
from .images import list_images
from .organizer import materialize_groups


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except ModuleNotFoundError as error:
        print(_dependency_error(error), file=sys.stderr)
        return 1
    except Exception as error:
        print(f"tihulu: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tihulu",
        description="Group photos by camera angle and render star trails.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser(
        "run",
        help="group photos and render one star trail per group",
    )
    add_input_output(run)
    add_grouping_options(run)
    add_output_options(run)
    add_stacking_options(run)
    add_timelapse_options(run, include_enable=True)
    run.set_defaults(func=run_command)

    group = subcommands.add_parser(
        "group",
        help="group photos without rendering star trails",
    )
    add_input_output(group)
    add_grouping_options(group)
    add_output_options(group)
    group.set_defaults(func=group_command)

    trail = subcommands.add_parser(
        "trail",
        help="render star trails from a folder or grouped output",
    )
    add_input_output(trail)
    add_stacking_options(trail)
    trail.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="scan image folders recursively when rendering a single trail",
    )
    trail.add_argument(
        "--quiet",
        action="store_true",
        help="hide progress output",
    )
    trail.set_defaults(func=trail_command)

    timelapse = subcommands.add_parser(
        "timelapse",
        help="render a timelapse video from photos or grouped output",
    )
    add_input_output(timelapse)
    add_timelapse_options(timelapse, include_enable=False)
    timelapse.add_argument(
        "--min-frames",
        type=int,
        default=2,
        help="minimum frames required before rendering a grouped timelapse",
    )
    timelapse.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="scan image folders recursively when rendering a single timelapse",
    )
    timelapse.add_argument(
        "--quiet",
        action="store_true",
        help="hide progress output",
    )
    timelapse.set_defaults(func=timelapse_command)

    ui = subcommands.add_parser(
        "ui",
        help="launch the local browser interface",
    )
    ui.add_argument("--host", default="127.0.0.1", help="host address to bind")
    ui.add_argument("--port", type=int, default=8765, help="port to bind")
    ui.add_argument(
        "--open",
        action="store_true",
        help="open the interface in the default browser",
    )
    ui.set_defaults(func=ui_command)

    desktop = subcommands.add_parser(
        "desktop",
        help="launch the native Debian/Pop!_OS desktop app",
    )
    desktop.add_argument(
        "--check",
        action="store_true",
        help="verify native desktop dependencies without opening a window",
    )
    desktop.set_defaults(func=desktop_command)

    return parser


def add_input_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, help="input image folder, SD card path, or file")
    parser.add_argument("output", type=Path, help="output folder or output image path")


def add_grouping_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_GROUPING_THRESHOLD,
        help="same-angle threshold from 0 to 1; higher is stricter",
    )
    parser.add_argument(
        "--min-matches",
        type=int,
        default=DEFAULT_MIN_MATCHES,
        help="minimum geometric feature matches expected for same-angle images",
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=DEFAULT_MAX_SIDE,
        help="longest image side used for grouping analysis",
    )
    parser.add_argument(
        "--nfeatures",
        type=int,
        default=DEFAULT_NFEATURES,
        help="maximum ORB features to detect per image",
    )
    parser.add_argument(
        "--time-metadata",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_TIME_METADATA,
        help="also require nearby EXIF or file metadata times when grouping",
    )
    parser.add_argument(
        "--time-window-minutes",
        type=float,
        default=DEFAULT_TIME_WINDOW_MINUTES,
        help="maximum metadata time gap allowed for same-group photos",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="scan input folders recursively",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="hide progress output",
    )


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--link-mode",
        choices=("symlink", "copy", "hardlink", "none"),
        default="symlink",
        help="how grouped photos are represented in the output folder",
    )


def add_stacking_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-frames",
        type=int,
        default=2,
        help="minimum frames required before rendering a group trail",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help="JPEG quality for rendered star trails",
    )


def add_timelapse_options(
    parser: argparse.ArgumentParser,
    include_enable: bool,
) -> None:
    if include_enable:
        parser.add_argument(
            "--timelapse",
            action="store_true",
            help="also render one timelapse video per detected group",
        )
    parser.add_argument(
        "--fps",
        type=float,
        default=24.0,
        help="timelapse frames per second",
    )
    parser.add_argument(
        "--video-max-side",
        type=int,
        default=1920,
        help="longest output video side; set 0 to keep original size",
    )
    parser.add_argument(
        "--codec",
        default="mp4v",
        help="four-character OpenCV video codec, usually mp4v or XVID",
    )


def run_command(args: argparse.Namespace) -> int:
    from .grouping import build_angle_groups
    from .stacker import render_group_timelapses, render_group_trails

    progress = None if args.quiet else _progress
    paths = _load_images(args.input, recursive=args.recursive)
    groups = build_angle_groups(
        paths,
        threshold=args.threshold,
        min_matches=args.min_matches,
        max_side=args.max_side,
        nfeatures=args.nfeatures,
        time_metadata=args.time_metadata,
        time_window_minutes=args.time_window_minutes,
        progress=progress,
    )
    manifest_path = materialize_groups(
        groups,
        args.output,
        link_mode=args.link_mode,
        threshold=args.threshold,
        time_metadata=args.time_metadata,
        time_window_minutes=args.time_window_minutes,
    )
    rendered = render_group_trails(
        groups,
        args.output / "trails",
        min_frames=args.min_frames,
        jpeg_quality=args.jpeg_quality,
        progress=progress,
    )
    videos = []
    if args.timelapse:
        videos = render_group_timelapses(
            groups,
            args.output / "timelapses",
            min_frames=args.min_frames,
            fps=args.fps,
            codec=args.codec,
            max_side=_optional_max_side(args.video_max_side),
            progress=progress,
        )
    print(
        f"Created {len(groups)} group(s), {len(rendered)} trail(s), "
        f"{len(videos)} timelapse(s), and {manifest_path}",
        file=sys.stderr,
    )
    return 0


def group_command(args: argparse.Namespace) -> int:
    from .grouping import build_angle_groups

    progress = None if args.quiet else _progress
    paths = _load_images(args.input, recursive=args.recursive)
    groups = build_angle_groups(
        paths,
        threshold=args.threshold,
        min_matches=args.min_matches,
        max_side=args.max_side,
        nfeatures=args.nfeatures,
        time_metadata=args.time_metadata,
        time_window_minutes=args.time_window_minutes,
        progress=progress,
    )
    manifest_path = materialize_groups(
        groups,
        args.output,
        link_mode=args.link_mode,
        threshold=args.threshold,
        time_metadata=args.time_metadata,
        time_window_minutes=args.time_window_minutes,
    )
    print(f"Created {len(groups)} group(s) and {manifest_path}", file=sys.stderr)
    return 0


def trail_command(args: argparse.Namespace) -> int:
    from .stacker import (
        discover_group_dirs,
        render_trails_from_group_dirs,
        stack_lighten,
    )

    progress = None if args.quiet else _progress
    if args.input.is_dir() and discover_group_dirs(args.input):
        rendered = render_trails_from_group_dirs(
            args.input,
            args.output,
            min_frames=args.min_frames,
            jpeg_quality=args.jpeg_quality,
            progress=progress,
        )
        print(f"Created {len(rendered)} trail(s) in {args.output}", file=sys.stderr)
        return 0

    paths = _load_images(args.input, recursive=args.recursive)
    output_path = args.output
    if output_path.suffix == "":
        output_path = output_path / "star_trail.jpg"
    stack_lighten(
        paths,
        output_path,
        jpeg_quality=args.jpeg_quality,
        progress=progress,
    )
    print(f"Created {output_path}", file=sys.stderr)
    return 0


def timelapse_command(args: argparse.Namespace) -> int:
    from .stacker import (
        discover_group_dirs,
        render_timelapse,
        render_timelapses_from_group_dirs,
    )

    progress = None if args.quiet else _progress
    if args.input.is_dir() and discover_group_dirs(args.input):
        rendered = render_timelapses_from_group_dirs(
            args.input,
            args.output,
            min_frames=args.min_frames,
            fps=args.fps,
            codec=args.codec,
            max_side=_optional_max_side(args.video_max_side),
            progress=progress,
        )
        print(f"Created {len(rendered)} timelapse(s) in {args.output}", file=sys.stderr)
        return 0

    paths = _load_images(args.input, recursive=args.recursive)
    output_path = args.output
    if output_path.suffix == "":
        output_path = output_path / "timelapse.mp4"
    render_timelapse(
        paths,
        output_path,
        fps=args.fps,
        codec=args.codec,
        max_side=_optional_max_side(args.video_max_side),
        progress=progress,
    )
    print(f"Created {output_path}", file=sys.stderr)
    return 0


def ui_command(args: argparse.Namespace) -> int:
    from .ui import serve_ui

    serve_ui(host=args.host, port=args.port, open_browser=args.open)
    return 0


def desktop_command(args: argparse.Namespace) -> int:
    from .desktop import check_desktop_dependencies, launch_desktop

    if args.check:
        check_desktop_dependencies()
        print("Tihulu native desktop dependencies are available.")
        return 0
    launch_desktop()
    return 0


def _load_images(path: Path, recursive: bool) -> list[Path]:
    paths = list_images(path, recursive=recursive)
    if not paths:
        raise ValueError(f"No supported images found in {path}")
    return paths


def _optional_max_side(value: int) -> int | None:
    return None if value <= 0 else value


def _progress(message: str) -> None:
    print(message, file=sys.stderr)


def _dependency_error(error: ModuleNotFoundError) -> str:
    package = error.name or str(error)
    apt_names = {
        "cv2": "python3-opencv",
        "numpy": "python3-numpy",
        "PIL": "python3-pillow",
        "rawpy": "rawpy is installed with pip; run: pip install rawpy",
        "tkinter": "python3-tk tk-dev",
        "_tkinter": "python3-tk tk-dev",
    }
    apt_name = apt_names.get(package)
    if apt_name and apt_name.startswith("python3-"):
        return (
            f"tihulu: missing dependency {package!r}. "
            f"On Debian/Pop!_OS, run: sudo apt install {apt_name}"
        )
    if apt_name:
        return f"tihulu: missing dependency {package!r}. {apt_name}"
    return f"tihulu: missing dependency {package!r}"


if __name__ == "__main__":
    raise SystemExit(main())
