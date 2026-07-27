#!/usr/bin/env python3
"""
DailyArchiveBackup
------------------
A local-first daily archival backup runner for BrisartPreservationTools.

This program creates scheduled archive snapshots using ArchiveSnapshot.py.

It does not connect to the internet.
It does not upload files.
It does not run hidden.
It only archives folders explicitly configured by the user.

Created by Jason Brisart
Part of BrisartPreservationTools
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from ArchiveSnapshot import (
    APP_VERSION as ARCHIVE_SNAPSHOT_VERSION,
    ArchiveSettings,
    create_archive_snapshot,
    human_bytes,
)


APP_NAME = "DailyArchiveBackup"
APP_VERSION = "1.0.0"
AUTHOR = "Jason Brisart"
REPOSITORY_NAME = "BrisartPreservationTools"

CONFIG_FILENAME = "DAILY_ARCHIVE_CONFIG.json"
LOG_FILENAME = "DAILY_ARCHIVE_LOG.md"
DEFAULT_STATE_FILENAME = "DAILY_ARCHIVE_STATE.json"


@dataclass(slots=True)
class DailyArchiveJob:
    """
    One configured daily archive job.
    """

    name: str
    source_folder: str
    archive_description: str = ""
    enabled: bool = True

    include_zip_snapshot: bool = True
    include_hashes: bool = True
    max_file_mb: float = 2000
    max_total_mb: float = 100000


@dataclass(slots=True)
class DailyArchiveConfig:
    """
    Daily archive configuration.
    """

    jobs: list[DailyArchiveJob] = field(default_factory=list)
    output_dir_name: str = "ARCHIVE_SNAPSHOTS"
    run_hour: int = 2
    run_minute: int = 0
    state_filename: str = DEFAULT_STATE_FILENAME
    log_filename: str = LOG_FILENAME

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "jobs": [asdict(job) for job in self.jobs],
            "output_dir_name": self.output_dir_name,
            "run_hour": self.run_hour,
            "run_minute": self.run_minute,
            "state_filename": self.state_filename,
            "log_filename": self.log_filename,
        }


def timestamp_now() -> str:
    """
    Return a timezone-aware timestamp.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def today_key() -> str:
    """
    Return today's local date key.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d")


def load_config(path: Path) -> DailyArchiveConfig:
    """
    Load daily archive config.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Create one with: py DailyArchiveBackup.py --init-config"
        )

    data = json.loads(path.read_text(encoding="utf-8"))

    jobs = []
    for item in data.get("jobs", []):
        jobs.append(
            DailyArchiveJob(
                name=item.get("name", ""),
                source_folder=item.get("source_folder", ""),
                archive_description=item.get("archive_description", ""),
                enabled=bool(item.get("enabled", True)),
                include_zip_snapshot=bool(item.get("include_zip_snapshot", True)),
                include_hashes=bool(item.get("include_hashes", True)),
                max_file_mb=float(item.get("max_file_mb", 2000)),
                max_total_mb=float(item.get("max_total_mb", 100000)),
            )
        )

    return DailyArchiveConfig(
        jobs=jobs,
        output_dir_name=data.get("output_dir_name", "ARCHIVE_SNAPSHOTS"),
        run_hour=int(data.get("run_hour", 2)),
        run_minute=int(data.get("run_minute", 0)),
        state_filename=data.get("state_filename", DEFAULT_STATE_FILENAME),
        log_filename=data.get("log_filename", LOG_FILENAME),
    )


def save_config(path: Path, config: DailyArchiveConfig) -> None:
    """
    Save config file.
    """
    path.write_text(
        json.dumps(config.to_jsonable(), indent=2),
        encoding="utf-8",
    )


def create_default_config(path: Path) -> None:
    """
    Create example config.
    """
    if path.exists():
        raise FileExistsError(f"Config already exists: {path}")

    example = DailyArchiveConfig(
        jobs=[
            DailyArchiveJob(
                name="Example Archive Job",
                source_folder=str(Path.cwd()),
                archive_description=(
                    "Example daily archival snapshot. Replace this with the folder "
                    "you want to preserve."
                ),
                enabled=False,
            )
        ],
        output_dir_name="ARCHIVE_SNAPSHOTS",
        run_hour=2,
        run_minute=0,
    )

    save_config(path, example)


def load_state(path: Path) -> dict[str, Any]:
    """
    Load state file.
    """
    if not path.exists():
        return {
            "last_run_by_job": {},
            "history": [],
        }

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_run_by_job": {},
            "history": [],
        }


def save_state(path: Path, state: dict[str, Any]) -> None:
    """
    Save state file.
    """
    path.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def append_log(path: Path, text: str) -> None:
    """
    Append to log file.
    """
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def run_job(job: DailyArchiveJob, config: DailyArchiveConfig) -> dict[str, Any]:
    """
    Run one archive job.
    """
    settings = ArchiveSettings(
        archive_name=job.name,
        archive_description=job.archive_description,
        output_dir_name=config.output_dir_name,
        include_zip_snapshot=job.include_zip_snapshot,
        include_hashes=job.include_hashes,
        max_file_bytes=int(job.max_file_mb * 1_000_000),
        max_total_bytes=int(job.max_total_mb * 1_000_000),
    )

    result = create_archive_snapshot(
        source_root=job.source_folder,
        settings=settings,
    )

    return {
        "job_name": job.name,
        "source_folder": job.source_folder,
        "created": timestamp_now(),
        "success": True,
        "export_dir": str(result.export_dir),
        "included_count": result.included_count,
        "skipped_count": result.skipped_count,
        "included_bytes": result.total_included_bytes,
        "included_size_readable": human_bytes(result.total_included_bytes),
        "summary_path": str(result.summary_path) if result.summary_path else "",
        "manifest_path": str(result.manifest_path) if result.manifest_path else "",
        "hashes_path": str(result.hashes_path) if result.hashes_path else "",
        "tree_path": str(result.tree_path) if result.tree_path else "",
        "zip_path": str(result.zip_path) if result.zip_path else "",
    }


def run_all_due_jobs(config_path: Path, force: bool = False) -> list[dict[str, Any]]:
    """
    Run all jobs that are due today.
    """
    config = load_config(config_path)

    state_path = config_path.parent / config.state_filename
    log_path = config_path.parent / config.log_filename

    state = load_state(state_path)
    last_run_by_job = state.setdefault("last_run_by_job", {})
    history = state.setdefault("history", [])

    date_key = today_key()
    results: list[dict[str, Any]] = []

    append_log(
        log_path,
        (
            f"\n## Daily Archive Run - {timestamp_now()}\n\n"
            f"- Tool: `{APP_NAME} v{APP_VERSION}`\n"
            f"- ArchiveSnapshot version: `{ARCHIVE_SNAPSHOT_VERSION}`\n"
            f"- Config: `{config_path}`\n"
            f"- Force run: `{force}`\n"
        ),
    )

    for job in config.jobs:
        if not job.enabled:
            append_log(log_path, f"- Skipped disabled job: `{job.name}`\n")
            continue

        if not job.name.strip():
            append_log(log_path, "- Skipped unnamed job.\n")
            continue

        if not job.source_folder.strip():
            append_log(log_path, f"- Skipped `{job.name}` because source folder is empty.\n")
            continue

        already_ran_today = last_run_by_job.get(job.name) == date_key

        if already_ran_today and not force:
            append_log(log_path, f"- Already ran today: `{job.name}`\n")
            continue

        try:
            result = run_job(job, config)
            results.append(result)

            last_run_by_job[job.name] = date_key
            history.append(result)

            append_log(
                log_path,
                (
                    f"### Job Complete: `{job.name}`\n\n"
                    f"- Source: `{job.source_folder}`\n"
                    f"- Export: `{result['export_dir']}`\n"
                    f"- Included files: `{result['included_count']}`\n"
                    f"- Skipped files: `{result['skipped_count']}`\n"
                    f"- Included size: `{result['included_size_readable']}`\n"
                ),
            )

        except Exception as exc:
            failure = {
                "job_name": job.name,
                "source_folder": job.source_folder,
                "created": timestamp_now(),
                "success": False,
                "error": str(exc),
            }

            results.append(failure)
            history.append(failure)

            append_log(
                log_path,
                (
                    f"### Job Failed: `{job.name}`\n\n"
                    f"- Source: `{job.source_folder}`\n"
                    f"- Error: `{exc}`\n"
                ),
            )

    save_state(state_path, state)
    return results


def should_run_now(config: DailyArchiveConfig, last_loop_date: str | None) -> bool:
    """
    Determine if the long-running watcher should trigger today.
    """
    now = datetime.datetime.now().astimezone()
    current_date = now.strftime("%Y-%m-%d")

    if last_loop_date == current_date:
        return False

    if now.hour > config.run_hour:
        return True

    if now.hour == config.run_hour and now.minute >= config.run_minute:
        return True

    return False


def watch_daily(config_path: Path) -> None:
    """
    Long-running local watcher.

    This does not install itself.
    This does not hide itself.
    It only runs while the user keeps it running.
    """
    print(f"{APP_NAME} v{APP_VERSION}")
    print("Daily watcher started.")
    print(f"Config: {config_path}")
    print("Press Ctrl+C to stop.")
    print()

    last_loop_date: str | None = None

    while True:
        try:
            config = load_config(config_path)

            if should_run_now(config, last_loop_date):
                print(f"[{timestamp_now()}] Running due archive jobs...")
                run_all_due_jobs(config_path, force=False)
                last_loop_date = today_key()
                print(f"[{timestamp_now()}] Daily archive pass complete.")

            time.sleep(30)

        except KeyboardInterrupt:
            print()
            print("Daily watcher stopped.")
            return

        except Exception as exc:
            print(f"[{timestamp_now()}] Error: {exc}")
            time.sleep(60)


def create_parser() -> argparse.ArgumentParser:
    """
    Create CLI parser.
    """
    parser = argparse.ArgumentParser(
        prog="DailyArchiveBackup.py",
        description="Create local daily archive snapshots from configured folders.",
    )

    parser.add_argument(
        "--config",
        default=CONFIG_FILENAME,
        help="Path to daily archive config JSON file.",
    )

    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create an example config file.",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run due jobs once and exit.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Run jobs even if they already ran today.",
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run as a visible daily watcher process.",
    )

    parser.add_argument(
        "--gui-config",
        action="store_true",
        help="Open simple config editor GUI.",
    )

    return parser


def run_gui_config(config_path: Path) -> None:
    """
    Simple Tkinter config editor.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} Config Editor")
    root.geometry("760x560")
    root.minsize(700, 520)

    config = None
    if config_path.exists():
        try:
            config = load_config(config_path)
        except Exception:
            config = None

    if config is None:
        config = DailyArchiveConfig()

    job_name = tk.StringVar(value="")
    source_folder = tk.StringVar(value="")
    description = tk.StringVar(value="")
    run_hour = tk.StringVar(value=str(config.run_hour))
    run_minute = tk.StringVar(value=str(config.run_minute))
    status = tk.StringVar(value=f"Config path: {config_path}")

    jobs_listbox: tk.Listbox | None = None

    def refresh_jobs() -> None:
        if jobs_listbox is None:
            return
        jobs_listbox.delete(0, tk.END)
        for job in config.jobs:
            flag = "enabled" if job.enabled else "disabled"
            jobs_listbox.insert(tk.END, f"{job.name} — {flag}")

    def browse_source() -> None:
        folder = filedialog.askdirectory(title="Select folder for daily archive")
        if folder:
            source_folder.set(folder)

    def add_job() -> None:
        name = job_name.get().strip()
        folder = source_folder.get().strip()

        if not name:
            messagebox.showerror("Missing Name", "Enter a job name.")
            return

        if not folder:
            messagebox.showerror("Missing Folder", "Select a source folder.")
            return

        config.jobs.append(
            DailyArchiveJob(
                name=name,
                source_folder=folder,
                archive_description=description.get().strip(),
                enabled=True,
            )
        )

        job_name.set("")
        source_folder.set("")
        description.set("")
        refresh_jobs()

    def save() -> None:
        try:
            config.run_hour = int(run_hour.get())
            config.run_minute = int(run_minute.get())

            if config.run_hour < 0 or config.run_hour > 23:
                raise ValueError("Run hour must be between 0 and 23.")

            if config.run_minute < 0 or config.run_minute > 59:
                raise ValueError("Run minute must be between 0 and 59.")

            save_config(config_path, config)
            status.set(f"Saved config: {config_path}")
            messagebox.showinfo("Config Saved", f"Saved:\n{config_path}")

        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))
            status.set(f"Save failed: {exc}")

    def remove_selected() -> None:
        if jobs_listbox is None:
            return

        selected = jobs_listbox.curselection()
        if not selected:
            return

        index = selected[0]
        if 0 <= index < len(config.jobs):
            del config.jobs[index]
            refresh_jobs()

    title = tk.Label(
        root,
        text=f"{APP_NAME} v{APP_VERSION}",
        font=("Segoe UI", 18, "bold"),
    )
    title.pack(pady=(16, 4))

    subtitle = tk.Label(
        root,
        text="Configure local daily archival snapshots.",
        wraplength=700,
        justify="center",
    )
    subtitle.pack(pady=(0, 12))

    schedule_frame = tk.LabelFrame(root, text="Daily Run Time")
    schedule_frame.pack(fill="x", padx=20, pady=(4, 8))

    tk.Label(schedule_frame, text="Hour 0-23:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
    tk.Entry(schedule_frame, textvariable=run_hour, width=8).grid(row=0, column=1, padx=8, pady=8, sticky="w")

    tk.Label(schedule_frame, text="Minute 0-59:").grid(row=0, column=2, padx=8, pady=8, sticky="w")
    tk.Entry(schedule_frame, textvariable=run_minute, width=8).grid(row=0, column=3, padx=8, pady=8, sticky="w")

    job_frame = tk.LabelFrame(root, text="Add Archive Job")
    job_frame.pack(fill="x", padx=20, pady=(4, 8))

    tk.Label(job_frame, text="Job Name").grid(row=0, column=0, padx=8, pady=6, sticky="w")
    tk.Entry(job_frame, textvariable=job_name, width=62).grid(row=0, column=1, padx=8, pady=6, sticky="ew")

    tk.Label(job_frame, text="Source Folder").grid(row=1, column=0, padx=8, pady=6, sticky="w")
    tk.Entry(job_frame, textvariable=source_folder, width=62).grid(row=1, column=1, padx=8, pady=6, sticky="ew")
    tk.Button(job_frame, text="Browse", command=browse_source).grid(row=1, column=2, padx=8, pady=6)

    tk.Label(job_frame, text="Description").grid(row=2, column=0, padx=8, pady=6, sticky="w")
    tk.Entry(job_frame, textvariable=description, width=62).grid(row=2, column=1, padx=8, pady=6, sticky="ew")

    tk.Button(job_frame, text="Add Job", command=add_job).grid(row=3, column=1, padx=8, pady=8, sticky="w")

    job_frame.columnconfigure(1, weight=1)

    list_frame = tk.LabelFrame(root, text="Configured Jobs")
    list_frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))

    jobs_listbox = tk.Listbox(list_frame, height=7)
    jobs_listbox.pack(fill="both", expand=True, padx=8, pady=8)

    tk.Button(list_frame, text="Remove Selected Job", command=remove_selected).pack(pady=(0, 8))

    button_frame = tk.Frame(root)
    button_frame.pack(fill="x", padx=20, pady=(4, 8))

    tk.Button(
        button_frame,
        text="Save Config",
        command=save,
        height=2,
        width=24,
        font=("Segoe UI", 10, "bold"),
    ).pack(side="left")

    status_label = tk.Label(root, textvariable=status, anchor="w", justify="left")
    status_label.pack(fill="x", padx=20, pady=(4, 10))

    refresh_jobs()
    root.mainloop()


def run_cli(args: list[str]) -> int:
    """
    Run CLI.
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    config_path = Path(parsed.config).expanduser().resolve()

    if parsed.init_config:
        create_default_config(config_path)
        print(f"Created example config: {config_path}")
        return 0

    if parsed.gui_config:
        run_gui_config(config_path)
        return 0

    if parsed.once:
        results = run_all_due_jobs(config_path, force=parsed.force)
        print(f"{APP_NAME} v{APP_VERSION}")
        print("Run complete.")
        print(f"Jobs processed: {len(results)}")
        for result in results:
            if result.get("success"):
                print(f"- {result.get('job_name')}: {result.get('export_dir')}")
            else:
                print(f"- {result.get('job_name')}: FAILED - {result.get('error')}")
        return 0

    if parsed.watch:
        watch_daily(config_path)
        return 0

    parser.print_help()
    return 0


def main() -> None:
    """
    Main entry point.
    """
    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()