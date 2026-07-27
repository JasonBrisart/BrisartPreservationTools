#!/usr/bin/env python3
"""
ArchiveTimeline launcher.
Part of BrisartPreservationTools.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from constants import APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_NAME
from models import ArchiveSettings
from snapshot_engine import create_snapshot
from exporters import human_bytes
from gui import run_gui


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=f"{APP_NAME} v{APP_VERSION}",
    )

    parser.add_argument(
        "folder",
        nargs="?",
        help="Folder to archive. If omitted, GUI opens.",
    )

    parser.add_argument(
        "--name",
        default="",
        help="Archive name.",
    )

    parser.add_argument(
        "--description",
        default="",
        help="Archive description.",
    )

    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Do not create ZIP snapshot.",
    )

    parser.add_argument(
        "--no-hashes",
        action="store_true",
        help="Do not generate SHA256 hashes.",
    )

    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Do not generate change report against previous snapshot.",
    )

    parser.add_argument(
        "--max-file-mb",
        type=float,
        default=2000,
    )

    parser.add_argument(
        "--max-total-mb",
        type=float,
        default=100000,
    )

    return parser


def run_cli(args: list[str]) -> int:
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.folder:
        run_gui()
        return 0

    settings = ArchiveSettings(
        archive_name=parsed.name,
        archive_description=parsed.description,
        include_zip_snapshot=not parsed.no_zip,
        include_hashes=not parsed.no_hashes,
        include_diff_report=not parsed.no_diff,
        max_file_bytes=int(parsed.max_file_mb * 1_000_000),
        max_total_bytes=int(parsed.max_total_mb * 1_000_000),
    )

    result = create_snapshot(Path(parsed.folder), settings=settings)

    print(f"{APP_NAME} v{APP_VERSION}")
    print(f"Created by {AUTHOR}")
    print(f"Part of {REPOSITORY_NAME}")
    print()
    print("Archive snapshot complete.")
    print(f"Export folder : {result.export_dir}")
    print(f"Included files: {result.included_count}")
    print(f"Skipped files : {result.skipped_count}")
    print(f"Included size : {human_bytes(result.total_included_bytes)}")

    if result.summary_path:
        print(f"Summary       : {result.summary_path}")
    if result.manifest_path:
        print(f"Manifest      : {result.manifest_path}")
    if result.hashes_path:
        print(f"Hashes        : {result.hashes_path}")
    if result.tree_path:
        print(f"Folder tree   : {result.tree_path}")
    if result.diff_path:
        print(f"Diff report   : {result.diff_path}")
    if result.zip_path:
        print(f"ZIP snapshot  : {result.zip_path}")

    return 0


def main() -> None:
    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()