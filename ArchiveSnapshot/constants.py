"""
ArchiveTimeline constants.
Part of BrisartPreservationTools.
"""

APP_NAME = "ArchiveTimeline"
APP_VERSION = "1.0.0"
AUTHOR = "Jason Brisart"
REPOSITORY_NAME = "BrisartPreservationTools"

APP_TAGLINE = (
    "Local-first calendar-based archival timeline tool for preserving "
    "digital collections over time."
)

TIMELINE_DIRNAME = "ARCHIVE_TIMELINE"

SUMMARY_FILENAME = "ARCHIVE_SUMMARY.md"
MANIFEST_FILENAME = "ARCHIVE_MANIFEST.json"
HASHES_FILENAME = "HASHES.sha256"
TREE_FILENAME = "FOLDER_TREE.txt"
SETTINGS_FILENAME = "ARCHIVE_SETTINGS.json"
ZIP_FILENAME = "ARCHIVE_FILES.zip"
DIFF_FILENAME = "CHANGES_SINCE_PREVIOUS.md"
TIMELINE_INDEX_FILENAME = "TIMELINE_INDEX.json"
TIMELINE_LOG_FILENAME = "TIMELINE_LOG.md"
DAILY_STATE_FILENAME = "DAILY_ARCHIVE_STATE.json"
APP_SETTINGS_FILENAME = "ARCHIVE_TIMELINE_APP_SETTINGS.json"

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    TIMELINE_DIRNAME,
}

DEFAULT_EXCLUDED_FILES = {
    SUMMARY_FILENAME,
    MANIFEST_FILENAME,
    HASHES_FILENAME,
    TREE_FILENAME,
    SETTINGS_FILENAME,
    ZIP_FILENAME,
    DIFF_FILENAME,
    TIMELINE_INDEX_FILENAME,
    TIMELINE_LOG_FILENAME,
    DAILY_STATE_FILENAME,
    APP_SETTINGS_FILENAME,
}

DEFAULT_EXCLUDED_SUFFIXES = {
    ".tmp",
    ".temp",
    ".lock",
    ".pyc",
    ".pyo",
}