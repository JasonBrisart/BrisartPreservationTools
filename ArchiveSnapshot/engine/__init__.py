"""
engine
------
Core, non-UI logic for ArchiveSnapshot: scanning, snapshot creation,
timeline discovery, change reports, integrity verification, and Project
Context Helper import.

This package has no Tkinter or CLI dependency and can be reused by the
GUI (ui/), the headless daily runner (automation/), or any future
front-end without modification.

Common entry points are re-exported here for convenience:

    from engine import create_snapshot, ArchiveSettings
"""
from .app_info import APP_NAME, APP_VERSION, APP_TAGLINE, AUTHOR, REPOSITORY_NAME
from .settings import ArchiveSettings, AppSettings, TimelineSnapshot, SnapshotResult
from .snapshot_builder import create_snapshot
from .timeline_index import discover_snapshots, snapshots_by_date, write_timeline_index
from .change_report import compare_snapshot_dirs, build_diff_markdown
from .integrity_check import verify_snapshot_against_source, build_verify_report
from .snapshot_writer import human_bytes
from .project_context_import import (
    ensure_project_context_active_dir,
    project_context_active_dir,
    project_context_display_text,
)

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "APP_TAGLINE",
    "AUTHOR",
    "REPOSITORY_NAME",
    "ArchiveSettings",
    "AppSettings",
    "TimelineSnapshot",
    "SnapshotResult",
    "create_snapshot",
    "discover_snapshots",
    "snapshots_by_date",
    "write_timeline_index",
    "compare_snapshot_dirs",
    "build_diff_markdown",
    "verify_snapshot_against_source",
    "build_verify_report",
    "human_bytes",
    "ensure_project_context_active_dir",
    "project_context_active_dir",
    "project_context_display_text",
]