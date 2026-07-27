#!/usr/bin/env python3
"""
ArchiveSnapshot
---------------
A local-first archival snapshot utility for BrisartPreservationTools.

ArchiveSnapshot captures the state of a selected folder at a specific moment
in time and generates preservation-focused records:

- ARCHIVE_SUMMARY.md
- ARCHIVE_MANIFEST.json
- HASHES.sha256
- FOLDER_TREE.txt
- Optional ZIP snapshot

This is not cloud backup software.
This is an archival snapshot tool.

Purpose:
Preserve the artifact.
Preserve the context.
Preserve the history.

Created by Jason Brisart
Part of BrisartPreservationTools
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


APP_NAME = "ArchiveSnapshot"
APP_VERSION = "1.0.0"
AUTHOR = "Jason Brisart"
REPOSITORY_NAME = "BrisartPreservationTools"

DEFAULT_OUTPUT_DIRNAME = "ARCHIVE_SNAPSHOTS"

SUMMARY_FILENAME = "ARCHIVE_SUMMARY.md"
MANIFEST_FILENAME = "ARCHIVE_MANIFEST.json"
HASHES_FILENAME = "HASHES.sha256"
TREE_FILENAME = "FOLDER_TREE.txt"
SETTINGS_FILENAME = "ARCHIVE_SETTINGS.json"
SNAPSHOT_ZIP_FILENAME = "ARCHIVE_FILES.zip"

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
    DEFAULT_OUTPUT_DIRNAME,
}

DEFAULT_EXCLUDED_FILES = {
    SUMMARY_FILENAME,
    MANIFEST_FILENAME,
    HASHES_FILENAME,
    TREE_FILENAME,
    SETTINGS_FILENAME,
    SNAPSHOT_ZIP_FILENAME,
}

DEFAULT_EXCLUDED_SUFFIXES = {
    ".tmp",
    ".temp",
    ".lock",
    ".pyc",
    ".pyo",
    ".log",
}


@dataclass(slots=True)
class ArchiveSettings:
    """
    User-adjustable settings for an archival snapshot.
    """

    archive_name: str = ""
    archive_description: str = ""
    output_dir_name: str = DEFAULT_OUTPUT_DIRNAME

    include_hashes: bool = True
    include_zip_snapshot: bool = True
    include_folder_tree: bool = True
    include_manifest: bool = True
    include_summary: bool = True

    max_file_bytes: int = 2_000_000_000
    max_total_bytes: int = 100_000_000_000

    excluded_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_DIRS))
    excluded_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_FILES))
    excluded_suffixes: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_SUFFIXES))

    def to_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        data["excluded_dirs"] = sorted(self.excluded_dirs)
        data["excluded_files"] = sorted(self.excluded_files)
        data["excluded_suffixes"] = sorted(self.excluded_suffixes)
        return data


@dataclass(slots=True)
class ArchiveFileRecord:
    """
    Metadata for a file included in the archive snapshot.
    """

    relative_path: str
    size_bytes: int
    modified_time: str
    extension: str
    sha256: str | None = None


@dataclass(slots=True)
class SkippedFileRecord:
    """
    Metadata for skipped files.
    """

    relative_path: str
    reason: str
    size_bytes: int | None = None


@dataclass(slots=True)
class ArchiveScanResult:
    """
    Result of scanning a folder for archival snapshot creation.
    """

    included_paths: list[Path]
    included_records: list[ArchiveFileRecord]
    skipped_records: list[SkippedFileRecord]
    total_included_bytes: int


@dataclass(slots=True)
class ArchiveBuildResult:
    """
    Final result of an archive snapshot build.
    """

    export_dir: Path
    summary_path: Path | None
    manifest_path: Path | None
    hashes_path: Path | None
    tree_path: Path | None
    settings_path: Path
    zip_path: Path | None
    included_count: int
    skipped_count: int
    total_included_bytes: int


def timestamp_now() -> str:
    """
    Return a timezone-aware timestamp.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def timestamp_slug() -> str:
    """
    Return a filesystem-safe timestamp.
    """
    return datetime.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def validate_root(path_value: str | Path) -> Path:
    """
    Resolve and validate an archive source folder.
    """
    root = Path(path_value).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"Archive source folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Archive source path is not a folder: {root}")

    return root


def relative_string(path: Path, root: Path) -> str:
    """
    Return a safe relative path string.
    """
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_size(path: Path) -> int | None:
    """
    Return file size or None if unavailable.
    """
    try:
        return path.stat().st_size
    except OSError:
        return None


def modified_time(path: Path) -> str:
    """
    Return file modified time as a readable timestamp.
    """
    try:
        value = datetime.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        return value.strftime("%Y-%m-%d %H:%M:%S %z")
    except OSError:
        return ""


def sha256_file(path: Path) -> str | None:
    """
    Generate a SHA256 checksum for a file.
    """
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def exclusion_reason(path: Path, root: Path, settings: ArchiveSettings) -> str | None:
    """
    Return a reason if the path should be excluded.
    """
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return "outside_root"

    for part in relative_parts:
        if part in settings.excluded_dirs:
            return f"excluded_directory:{part}"

    if path.name in settings.excluded_files:
        return f"excluded_file:{path.name}"

    suffix = path.suffix.lower()
    if suffix in settings.excluded_suffixes:
        return f"excluded_suffix:{suffix}"

    return None


def should_include_file(
    path: Path,
    root: Path,
    settings: ArchiveSettings,
    current_total_bytes: int,
) -> tuple[bool, SkippedFileRecord | None]:
    """
    Decide whether a file should be included.
    """
    relative_path = relative_string(path, root)

    if not path.is_file():
        return False, None

    reason = exclusion_reason(path, root, settings)
    if reason:
        return False, SkippedFileRecord(
            relative_path=relative_path,
            reason=reason,
            size_bytes=safe_size(path),
        )

    size = safe_size(path)
    if size is None:
        return False, SkippedFileRecord(
            relative_path=relative_path,
            reason="size_unavailable",
            size_bytes=None,
        )

    if size > settings.max_file_bytes:
        return False, SkippedFileRecord(
            relative_path=relative_path,
            reason="file_too_large",
            size_bytes=size,
        )

    if current_total_bytes + size > settings.max_total_bytes:
        return False, SkippedFileRecord(
            relative_path=relative_path,
            reason="total_size_limit",
            size_bytes=size,
        )

    return True, None


def scan_archive(root: Path, settings: ArchiveSettings) -> ArchiveScanResult:
    """
    Scan the archive source folder.
    """
    included_paths: list[Path] = []
    included_records: list[ArchiveFileRecord] = []
    skipped_records: list[SkippedFileRecord] = []
    total_bytes = 0

    for path in sorted(root.rglob("*")):
        include, skip = should_include_file(
            path=path,
            root=root,
            settings=settings,
            current_total_bytes=total_bytes,
        )

        if skip is not None:
            skipped_records.append(skip)
            continue

        if not include:
            continue

        size = safe_size(path)
        if size is None:
            skipped_records.append(
                SkippedFileRecord(
                    relative_path=relative_string(path, root),
                    reason="size_unavailable",
                    size_bytes=None,
                )
            )
            continue

        checksum = sha256_file(path) if settings.include_hashes else None

        included_paths.append(path)
        included_records.append(
            ArchiveFileRecord(
                relative_path=relative_string(path, root),
                size_bytes=size,
                modified_time=modified_time(path),
                extension=path.suffix.lower() or path.name.lower(),
                sha256=checksum,
            )
        )
        total_bytes += size

    return ArchiveScanResult(
        included_paths=included_paths,
        included_records=included_records,
        skipped_records=skipped_records,
        total_included_bytes=total_bytes,
    )


def human_bytes(value: int) -> str:
    """
    Convert bytes into a readable size string.
    """
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)

    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}"
        amount /= 1024

    return f"{value} B"


def build_folder_tree(root: Path, settings: ArchiveSettings) -> str:
    """
    Build a readable folder tree.
    """
    lines: list[str] = [root.name + "/"]

    def walk(directory: Path, prefix: str = "") -> None:
        try:
            entries = sorted(
                [
                    entry
                    for entry in directory.iterdir()
                    if not exclusion_reason(entry, root, settings)
                ],
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
        except OSError:
            return

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            label = entry.name + "/" if entry.is_dir() else entry.name

            lines.append(prefix + connector + label)

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension)

    walk(root)
    return "\n".join(lines)


def build_manifest(
    root: Path,
    scan: ArchiveScanResult,
    settings: ArchiveSettings,
    created: str,
) -> dict[str, Any]:
    """
    Build machine-readable archive metadata.
    """
    extension_counts: dict[str, int] = {}

    for record in scan.included_records:
        extension_counts[record.extension] = extension_counts.get(record.extension, 0) + 1

    return {
        "created": created,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "author": AUTHOR,
        "repository_name": REPOSITORY_NAME,
        "archive_name": settings.archive_name,
        "archive_description": settings.archive_description,
        "source_root": str(root),
        "settings": settings.to_jsonable(),
        "summary": {
            "included_count": len(scan.included_records),
            "skipped_count": len(scan.skipped_records),
            "included_bytes": scan.total_included_bytes,
            "included_size_readable": human_bytes(scan.total_included_bytes),
            "extension_counts": dict(sorted(extension_counts.items())),
        },
        "included_files": [asdict(record) for record in scan.included_records],
        "skipped_files": [asdict(record) for record in scan.skipped_records],
    }


def build_summary_markdown(
    root: Path,
    scan: ArchiveScanResult,
    settings: ArchiveSettings,
    created: str,
) -> str:
    """
    Build human-readable archive summary.
    """
    extension_counts: dict[str, int] = {}

    for record in scan.included_records:
        extension_counts[record.extension] = extension_counts.get(record.extension, 0) + 1

    lines: list[str] = []

    title = settings.archive_name.strip() or root.name

    lines.append(f"# Archive Snapshot: {title}")
    lines.append("")
    lines.append(f"Generated: `{created}`")
    lines.append(f"Generated by: `{APP_NAME} v{APP_VERSION}`")
    lines.append(f"Author: `{AUTHOR}`")
    lines.append(f"Part of: `{REPOSITORY_NAME}`")
    lines.append("")
    lines.append("## Archive Description")
    lines.append("")
    if settings.archive_description.strip():
        lines.append(settings.archive_description.strip())
    else:
        lines.append("_No archive description provided._")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- Source folder: `{root}`")
    lines.append("")
    lines.append("## Snapshot Summary")
    lines.append("")
    lines.append(f"- Included files: `{len(scan.included_records)}`")
    lines.append(f"- Skipped files: `{len(scan.skipped_records)}`")
    lines.append(f"- Included size: `{human_bytes(scan.total_included_bytes)}`")
    lines.append(f"- Hashes included: `{settings.include_hashes}`")
    lines.append(f"- ZIP snapshot included: `{settings.include_zip_snapshot}`")
    lines.append("")
    lines.append("## File Types")
    lines.append("")

    if extension_counts:
        for ext, count in sorted(extension_counts.items()):
            lines.append(f"- `{ext}`: {count}")
    else:
        lines.append("- No files included.")

    lines.append("")
    lines.append("## Preservation Notes")
    lines.append("")
    lines.append(
        "This archive snapshot is intended to preserve a record of what existed "
        "inside the selected folder at the time the snapshot was created."
    )
    lines.append("")
    lines.append(
        "Use the manifest, hashes, and folder tree to inspect archive contents, "
        "verify file integrity, and understand the historical state of the collection."
    )
    lines.append("")
    lines.append("## Generated Files")
    lines.append("")
    lines.append(f"- `{SUMMARY_FILENAME}`")
    lines.append(f"- `{MANIFEST_FILENAME}`")
    lines.append(f"- `{HASHES_FILENAME}`")
    lines.append(f"- `{TREE_FILENAME}`")
    lines.append(f"- `{SETTINGS_FILENAME}`")
    if settings.include_zip_snapshot:
        lines.append(f"- `{SNAPSHOT_ZIP_FILENAME}`")

    return "\n".join(lines)


def build_hashes_text(scan: ArchiveScanResult) -> str:
    """
    Build HASHES.sha256 contents.
    """
    lines: list[str] = []

    for record in scan.included_records:
        if not record.sha256:
            continue
        normalized_path = record.relative_path.replace("\\", "/")
        lines.append(f"{record.sha256}  {normalized_path}")

    return "\n".join(lines) + ("\n" if lines else "")


def create_zip_snapshot(
    zip_path: Path,
    root: Path,
    scan: ArchiveScanResult,
    generated_files: list[Path],
) -> None:
    """
    Create ZIP package containing generated records and included files.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for generated_file in generated_files:
            if generated_file.exists():
                archive.write(generated_file, generated_file.name)

        for path in scan.included_paths:
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = path.name
            archive.write(path, f"archive_files/{rel}")


def create_archive_snapshot(
    source_root: str | Path,
    settings: ArchiveSettings | None = None,
) -> ArchiveBuildResult:
    """
    Create a complete archive snapshot.
    """
    root = validate_root(source_root)
    settings = settings or ArchiveSettings()

    created = timestamp_now()
    export_dir = root / settings.output_dir_name / f"archive_snapshot_{timestamp_slug()}"
    export_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_archive(root, settings)

    summary_path = export_dir / SUMMARY_FILENAME if settings.include_summary else None
    manifest_path = export_dir / MANIFEST_FILENAME if settings.include_manifest else None
    hashes_path = export_dir / HASHES_FILENAME if settings.include_hashes else None
    tree_path = export_dir / TREE_FILENAME if settings.include_folder_tree else None
    settings_path = export_dir / SETTINGS_FILENAME
    zip_path = export_dir / SNAPSHOT_ZIP_FILENAME if settings.include_zip_snapshot else None

    generated_files: list[Path] = []

    if summary_path:
        summary_path.write_text(
            build_summary_markdown(root, scan, settings, created),
            encoding="utf-8",
        )
        generated_files.append(summary_path)

    if manifest_path:
        manifest_path.write_text(
            json.dumps(
                build_manifest(root, scan, settings, created),
                indent=2,
            ),
            encoding="utf-8",
        )
        generated_files.append(manifest_path)

    if hashes_path:
        hashes_path.write_text(
            build_hashes_text(scan),
            encoding="utf-8",
        )
        generated_files.append(hashes_path)

    if tree_path:
        tree_path.write_text(
            build_folder_tree(root, settings),
            encoding="utf-8",
        )
        generated_files.append(tree_path)

    settings_path.write_text(
        json.dumps(settings.to_jsonable(), indent=2),
        encoding="utf-8",
    )
    generated_files.append(settings_path)

    if zip_path is not None:
        create_zip_snapshot(
            zip_path=zip_path,
            root=root,
            scan=scan,
            generated_files=generated_files,
        )

    return ArchiveBuildResult(
        export_dir=export_dir,
        summary_path=summary_path,
        manifest_path=manifest_path,
        hashes_path=hashes_path,
        tree_path=tree_path,
        settings_path=settings_path,
        zip_path=zip_path,
        included_count=len(scan.included_records),
        skipped_count=len(scan.skipped_records),
        total_included_bytes=scan.total_included_bytes,
    )


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line parser.
    """
    parser = argparse.ArgumentParser(
        prog="ArchiveSnapshot.py",
        description="Create a local archival snapshot of a selected folder.",
    )

    parser.add_argument(
        "source",
        nargs="?",
        help="Folder to preserve. If omitted, GUI mode opens.",
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
        "--output-dir",
        default=DEFAULT_OUTPUT_DIRNAME,
        help="Output directory name inside the source folder.",
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
        "--max-file-mb",
        type=float,
        default=2000,
        help="Maximum file size in MB.",
    )

    parser.add_argument(
        "--max-total-mb",
        type=float,
        default=100000,
        help="Maximum total included size in MB.",
    )

    return parser


def run_cli(args: list[str]) -> int:
    """
    Run command-line workflow.
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.source:
        run_gui()
        return 0

    settings = ArchiveSettings(
        archive_name=parsed.name,
        archive_description=parsed.description,
        output_dir_name=parsed.output_dir,
        include_zip_snapshot=not parsed.no_zip,
        include_hashes=not parsed.no_hashes,
        max_file_bytes=int(parsed.max_file_mb * 1_000_000),
        max_total_bytes=int(parsed.max_total_mb * 1_000_000),
    )

    result = create_archive_snapshot(parsed.source, settings=settings)

    print(f"{APP_NAME} v{APP_VERSION}")
    print("Archive snapshot complete.")
    print()
    print(f"Export folder: {result.export_dir}")
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
    if result.zip_path:
        print(f"ZIP snapshot  : {result.zip_path}")

    return 0


def run_gui() -> None:
    """
    Launch a simple Tkinter GUI.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("760x560")
    root.minsize(700, 520)

    selected_folder = tk.StringVar(value=str(Path.cwd()))
    archive_name = tk.StringVar(value="")
    archive_description = tk.StringVar(value="")
    output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIRNAME)

    include_zip = tk.BooleanVar(value=True)
    include_hashes = tk.BooleanVar(value=True)
    include_tree = tk.BooleanVar(value=True)

    max_file_mb = tk.StringVar(value="2000")
    max_total_mb = tk.StringVar(value="100000")

    status = tk.StringVar(value="Select a folder and create an archival snapshot.")

    def browse_folder() -> None:
        folder = filedialog.askdirectory(
            initialdir=selected_folder.get(),
            title="Select folder to preserve",
        )
        if folder:
            selected_folder.set(folder)

    def build_snapshot() -> None:
        try:
            status.set("Creating archive snapshot...")
            root.update_idletasks()

            try:
                max_file_bytes = int(float(max_file_mb.get()) * 1_000_000)
            except ValueError:
                raise ValueError("Max File MB must be numeric.")

            try:
                max_total_bytes = int(float(max_total_mb.get()) * 1_000_000)
            except ValueError:
                raise ValueError("Max Total MB must be numeric.")

            settings = ArchiveSettings(
                archive_name=archive_name.get().strip(),
                archive_description=archive_description.get().strip(),
                output_dir_name=output_dir.get().strip() or DEFAULT_OUTPUT_DIRNAME,
                include_zip_snapshot=include_zip.get(),
                include_hashes=include_hashes.get(),
                include_folder_tree=include_tree.get(),
                max_file_bytes=max_file_bytes,
                max_total_bytes=max_total_bytes,
            )

            result = create_archive_snapshot(
                selected_folder.get(),
                settings=settings,
            )

            status.set(
                "Archive snapshot complete.\n"
                f"Export folder: {result.export_dir}\n"
                f"Included files: {result.included_count}\n"
                f"Included size: {human_bytes(result.total_included_bytes)}"
            )

            messagebox.showinfo(
                "Archive Snapshot Complete",
                (
                    f"Export folder:\n{result.export_dir}\n\n"
                    f"Included files: {result.included_count}\n"
                    f"Skipped files: {result.skipped_count}\n"
                    f"Included size: {human_bytes(result.total_included_bytes)}"
                ),
            )

        except Exception as exc:
            status.set(f"Snapshot failed: {exc}")
            messagebox.showerror("Archive Snapshot Failed", str(exc))

    header = tk.Label(
        root,
        text=f"{APP_NAME} v{APP_VERSION}",
        font=("Segoe UI", 18, "bold"),
    )
    header.pack(pady=(16, 4))

    subtitle = tk.Label(
        root,
        text=(
            "Local-first archival snapshot utility.\n"
            "Preserve the artifact, preserve the context, preserve the history."
        ),
        justify="center",
        wraplength=700,
    )
    subtitle.pack(pady=(0, 12))

    form = tk.Frame(root)
    form.pack(fill="x", padx=24)

    padding = {"padx": 8, "pady": 6}

    tk.Label(form, text="Folder to Preserve").grid(row=0, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=selected_folder, width=72).grid(row=0, column=1, sticky="ew", **padding)
    tk.Button(form, text="Browse", command=browse_folder).grid(row=0, column=2, **padding)

    tk.Label(form, text="Archive Name").grid(row=1, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=archive_name, width=72).grid(row=1, column=1, columnspan=2, sticky="ew", **padding)

    tk.Label(form, text="Description").grid(row=2, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=archive_description, width=72).grid(row=2, column=1, columnspan=2, sticky="ew", **padding)

    tk.Label(form, text="Output Folder").grid(row=3, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=output_dir, width=72).grid(row=3, column=1, columnspan=2, sticky="ew", **padding)

    tk.Label(form, text="Max File MB").grid(row=4, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=max_file_mb, width=16).grid(row=4, column=1, sticky="w", **padding)

    tk.Label(form, text="Max Total MB").grid(row=5, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=max_total_mb, width=16).grid(row=5, column=1, sticky="w", **padding)

    options = tk.LabelFrame(root, text="Snapshot Options")
    options.pack(fill="x", padx=24, pady=(14, 8))

    tk.Checkbutton(options, text="Create ZIP Snapshot", variable=include_zip).pack(anchor="w", padx=12, pady=3)
    tk.Checkbutton(options, text="Generate SHA256 Hashes", variable=include_hashes).pack(anchor="w", padx=12, pady=3)
    tk.Checkbutton(options, text="Generate Folder Tree", variable=include_tree).pack(anchor="w", padx=12, pady=3)

    build_button = tk.Button(
        root,
        text="Create Archive Snapshot",
        command=build_snapshot,
        height=2,
        width=30,
        font=("Segoe UI", 11, "bold"),
    )
    build_button.pack(pady=(16, 8))

    status_label = tk.Label(
        root,
        textvariable=status,
        justify="left",
        anchor="w",
        wraplength=700,
    )
    status_label.pack(fill="x", padx=24, pady=(6, 10))

    footer = tk.Label(
        root,
        text=f"Created by {AUTHOR}\nPart of {REPOSITORY_NAME}",
        fg="gray",
        font=("Segoe UI", 8),
        justify="center",
    )
    footer.pack(pady=(0, 8))

    form.columnconfigure(1, weight=1)

    root.mainloop()


def main() -> None:
    """
    Main entry point.
    """
    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()