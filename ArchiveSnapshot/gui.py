"""
Tkinter GUI for ArchiveTimeline.
"""

from __future__ import annotations

import calendar
import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from constants import (
    APP_NAME,
    APP_VERSION,
    APP_TAGLINE,
    AUTHOR,
    REPOSITORY_NAME,
    APP_SETTINGS_FILENAME,
)
from diff_engine import build_diff_markdown, compare_snapshot_dirs
from exporters import human_bytes
from models import AppSettings, ArchiveSettings, TimelineSnapshot
from snapshot_engine import create_snapshot
from timeline import discover_snapshots, snapshots_by_date
from verifier import build_verify_report, verify_snapshot_against_source


def open_path(path: Path) -> None:
    """
    Open path in system file browser / default app.
    """
    try:
        os.startfile(path)
    except AttributeError:
        messagebox.showinfo("Path", str(path))
    except Exception as exc:
        messagebox.showerror("Open Failed", str(exc))


def app_settings_path() -> Path:
    """
    Return app settings path.
    """
    return Path.cwd() / APP_SETTINGS_FILENAME


def load_app_settings() -> AppSettings:
    """
    Load saved GUI settings.
    """
    path = app_settings_path()

    if not path.exists():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppSettings(
            selected_archive_folder=data.get("selected_archive_folder", ""),
            archive_name=data.get("archive_name", ""),
            archive_description=data.get("archive_description", ""),
            daily_mode_enabled=bool(data.get("daily_mode_enabled", False)),
            daily_run_hour=int(data.get("daily_run_hour", 2)),
            daily_run_minute=int(data.get("daily_run_minute", 0)),
            include_zip_snapshot=bool(data.get("include_zip_snapshot", True)),
            include_hashes=bool(data.get("include_hashes", True)),
            include_folder_tree=bool(data.get("include_folder_tree", True)),
            include_diff_report=bool(data.get("include_diff_report", True)),
            max_file_mb=float(data.get("max_file_mb", 2000)),
            max_total_mb=float(data.get("max_total_mb", 100000)),
        )
    except Exception:
        return AppSettings()


def save_app_settings(settings: AppSettings) -> None:
    """
    Save GUI settings.
    """
    app_settings_path().write_text(
        json.dumps(settings.to_jsonable(), indent=2),
        encoding="utf-8",
    )


class ArchiveTimelineGUI:
    """
    Calendar-based archive timeline GUI.
    """

    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title(f"{APP_NAME} v{APP_VERSION}")
        self.window.geometry("1040x760")
        self.window.minsize(920, 680)

        loaded = load_app_settings()

        self.selected_folder = tk.StringVar(value=loaded.selected_archive_folder)
        self.archive_name = tk.StringVar(value=loaded.archive_name)
        self.archive_description = tk.StringVar(value=loaded.archive_description)

        self.include_zip = tk.BooleanVar(value=loaded.include_zip_snapshot)
        self.include_hashes = tk.BooleanVar(value=loaded.include_hashes)
        self.include_tree = tk.BooleanVar(value=loaded.include_folder_tree)
        self.include_diff = tk.BooleanVar(value=loaded.include_diff_report)

        self.max_file_mb = tk.StringVar(value=str(loaded.max_file_mb))
        self.max_total_mb = tk.StringVar(value=str(loaded.max_total_mb))

        self.daily_enabled = tk.BooleanVar(value=loaded.daily_mode_enabled)
        self.daily_hour = tk.StringVar(value=str(loaded.daily_run_hour))
        self.daily_minute = tk.StringVar(value=str(loaded.daily_run_minute))

        self.status = tk.StringVar(value="Select an archive folder.")
        self.selected_snapshot: TimelineSnapshot | None = None

        today = __import__("datetime").datetime.datetime.now()
        self.current_year = today.year
        self.current_month = today.month

        self.calendar_buttons: list[tk.Button] = []
        self.snapshot_listbox: tk.Listbox | None = None
        self.detail_text: tk.Text | None = None

        self.build_ui()
        self.refresh_calendar()
        self.window.after(60000, self.daily_check_loop)

    def build_ui(self) -> None:
        header = tk.Label(
            self.window,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=("Segoe UI", 20, "bold"),
        )
        header.pack(pady=(14, 2))

        subtitle = tk.Label(
            self.window,
            text=f"{APP_TAGLINE}\nCreated by {AUTHOR} • Part of {REPOSITORY_NAME}",
            justify="center",
            fg="#555555",
        )
        subtitle.pack(pady=(0, 10))

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        self.tab_calendar = tk.Frame(notebook)
        self.tab_build = tk.Frame(notebook)
        self.tab_compare = tk.Frame(notebook)
        self.tab_verify = tk.Frame(notebook)
        self.tab_settings = tk.Frame(notebook)
        self.tab_about = tk.Frame(notebook)

        notebook.add(self.tab_calendar, text="Calendar")
        notebook.add(self.tab_build, text="Create Snapshot")
        notebook.add(self.tab_compare, text="Compare")
        notebook.add(self.tab_verify, text="Verify")
        notebook.add(self.tab_settings, text="Settings")
        notebook.add(self.tab_about, text="About")

        self.build_calendar_tab()
        self.build_snapshot_tab()
        self.build_compare_tab()
        self.build_verify_tab()
        self.build_settings_tab()
        self.build_about_tab()

        status_bar = tk.Label(
            self.window,
            textvariable=self.status,
            anchor="w",
            relief="sunken",
            padx=8,
        )
        status_bar.pack(side="bottom", fill="x")

    def build_folder_picker(self, parent: tk.Frame) -> None:
        frame = tk.LabelFrame(parent, text="Archive Folder", padx=10, pady=10)
        frame.pack(fill="x", padx=14, pady=10)

        tk.Entry(frame, textvariable=self.selected_folder).pack(side="left", fill="x", expand=True)

        tk.Button(frame, text="Browse", command=self.browse_folder).pack(side="left", padx=(8, 0))
        tk.Button(frame, text="Open", command=self.open_selected_folder).pack(side="left", padx=(8, 0))
        tk.Button(frame, text="Refresh", command=self.refresh_calendar).pack(side="left", padx=(8, 0))

    def build_calendar_tab(self) -> None:
        self.build_folder_picker(self.tab_calendar)

        nav = tk.Frame(self.tab_calendar)
        nav.pack(fill="x", padx=14, pady=(2, 8))

        tk.Button(nav, text="Previous Month", command=self.previous_month).pack(side="left")
        tk.Button(nav, text="Today", command=self.jump_today).pack(side="left", padx=8)
        tk.Button(nav, text="Next Month", command=self.next_month).pack(side="left")

        self.month_label = tk.Label(nav, text="", font=("Segoe UI", 14, "bold"))
        self.month_label.pack(side="left", padx=24)

        tk.Button(nav, text="Create Snapshot Today", command=self.create_snapshot_from_gui).pack(side="right")

        main = tk.Frame(self.tab_calendar)
        main.pack(fill="both", expand=True, padx=14, pady=8)

        calendar_frame = tk.LabelFrame(main, text="Archive Calendar")
        calendar_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.calendar_grid = tk.Frame(calendar_frame)
        self.calendar_grid.pack(fill="both", expand=True, padx=8, pady=8)

        right = tk.LabelFrame(main, text="Selected Date / Snapshot Details", width=360)
        right.pack(side="left", fill="both", padx=(8, 0))

        self.detail_text = tk.Text(right, height=18, wrap="word")
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=8)

        button_frame = tk.Frame(right)
        button_frame.pack(fill="x", padx=8, pady=(0, 8))

        tk.Button(button_frame, text="Open Snapshot Folder", command=self.open_selected_snapshot).pack(fill="x", pady=2)
        tk.Button(button_frame, text="Open Summary", command=lambda: self.open_file_in_snapshot("ARCHIVE_SUMMARY.md")).pack(fill="x", pady=2)
        tk.Button(button_frame, text="Open Manifest", command=lambda: self.open_file_in_snapshot("ARCHIVE_MANIFEST.json")).pack(fill="x", pady=2)
        tk.Button(button_frame, text="Open Folder Tree", command=lambda: self.open_file_in_snapshot("FOLDER_TREE.txt")).pack(fill="x", pady=2)
        tk.Button(button_frame, text="Open Diff Report", command=lambda: self.open_file_in_snapshot("CHANGES_SINCE_PREVIOUS.md")).pack(fill="x", pady=2)

    def build_snapshot_tab(self) -> None:
        self.build_folder_picker(self.tab_build)

        meta = tk.LabelFrame(self.tab_build, text="Snapshot Metadata", padx=10, pady=10)
        meta.pack(fill="x", padx=14, pady=8)

        tk.Label(meta, text="Archive Name").grid(row=0, column=0, sticky="w", pady=4)
        tk.Entry(meta, textvariable=self.archive_name, width=80).grid(row=0, column=1, sticky="ew", pady=4)

        tk.Label(meta, text="Description").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(meta, textvariable=self.archive_description, width=80).grid(row=1, column=1, sticky="ew", pady=4)

        meta.columnconfigure(1, weight=1)

        options = tk.LabelFrame(self.tab_build, text="Snapshot Options", padx=10, pady=10)
        options.pack(fill="x", padx=14, pady=8)

        tk.Checkbutton(options, text="Create ZIP Snapshot", variable=self.include_zip).pack(anchor="w")
        tk.Checkbutton(options, text="Generate SHA256 Hashes", variable=self.include_hashes).pack(anchor="w")
        tk.Checkbutton(options, text="Generate Folder Tree", variable=self.include_tree).pack(anchor="w")
        tk.Checkbutton(options, text="Generate Change Report Since Previous Snapshot", variable=self.include_diff).pack(anchor="w")

        limits = tk.LabelFrame(self.tab_build, text="Size Limits", padx=10, pady=10)
        limits.pack(fill="x", padx=14, pady=8)

        tk.Label(limits, text="Max File MB").grid(row=0, column=0, sticky="w")
        tk.Entry(limits, textvariable=self.max_file_mb, width=14).grid(row=0, column=1, sticky="w", padx=8)

        tk.Label(limits, text="Max Total MB").grid(row=1, column=0, sticky="w")
        tk.Entry(limits, textvariable=self.max_total_mb, width=14).grid(row=1, column=1, sticky="w", padx=8)

        tk.Button(
            self.tab_build,
            text="Create Archive Snapshot",
            command=self.create_snapshot_from_gui,
            height=2,
            width=32,
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=18)

    def build_compare_tab(self) -> None:
        self.build_folder_picker(self.tab_compare)

        info = tk.Label(
            self.tab_compare,
            text="Compare the two latest snapshots in the selected archive folder.",
            justify="left",
        )
        info.pack(anchor="w", padx=18, pady=12)

        tk.Button(
            self.tab_compare,
            text="Compare Two Latest Snapshots",
            command=self.compare_latest_two,
            height=2,
            width=32,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=8)

        self.compare_text = tk.Text(self.tab_compare, wrap="word")
        self.compare_text.pack(fill="both", expand=True, padx=18, pady=12)

    def build_verify_tab(self) -> None:
        self.build_folder_picker(self.tab_verify)

        tk.Label(
            self.tab_verify,
            text="Verify the latest snapshot against the current folder state.",
        ).pack(anchor="w", padx=18, pady=12)

        tk.Button(
            self.tab_verify,
            text="Verify Latest Snapshot",
            command=self.verify_latest_snapshot,
            height=2,
            width=32,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=8)

        self.verify_text = tk.Text(self.tab_verify, wrap="word")
        self.verify_text.pack(fill="both", expand=True, padx=18, pady=12)

    def build_settings_tab(self) -> None:
        self.build_folder_picker(self.tab_settings)

        daily = tk.LabelFrame(self.tab_settings, text="Daily Archive Mode", padx=10, pady=10)
        daily.pack(fill="x", padx=14, pady=12)

        tk.Checkbutton(
            daily,
            text="Enable daily archival snapshot while ArchiveTimeline is open",
            variable=self.daily_enabled,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=4)

        tk.Label(daily, text="Run Hour 0-23").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(daily, textvariable=self.daily_hour, width=8).grid(row=1, column=1, sticky="w", pady=4)

        tk.Label(daily, text="Run Minute 0-59").grid(row=1, column=2, sticky="w", padx=(18, 0), pady=4)
        tk.Entry(daily, textvariable=self.daily_minute, width=8).grid(row=1, column=3, sticky="w", pady=4)

        tk.Button(
            self.tab_settings,
            text="Save Settings",
            command=self.save_settings_from_gui,
            height=2,
            width=26,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=10)

    def build_about_tab(self) -> None:
        text = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "ArchiveTimeline is a local-first calendar-based archival timeline "
            "tool for preserving the state of important digital collections over time.\n\n"
            "It is designed to answer:\n\n"
            "What existed here on this date?\n"
            "How was it organized?\n"
            "What changed over time?\n"
            "Can the preserved files be verified?\n\n"
            "How this differs from Project Context Helper:\n\n"
            "Project Context Helper explains a software project.\n"
            "ArchiveTimeline preserves a historical record.\n\n"
            "Project Context Helper asks:\n"
            "What does this codebase look like right now?\n\n"
            "ArchiveTimeline asks:\n"
            "What existed here on this date, and how did it change over time?\n\n"
            f"Created by {AUTHOR}\n"
            f"Part of {REPOSITORY_NAME}"
        )

        label = tk.Label(
            self.tab_about,
            text=text,
            justify="left",
            anchor="nw",
            wraplength=820,
        )
        label.pack(fill="both", expand=True, padx=22, pady=22)

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select archive folder")
        if folder:
            self.selected_folder.set(folder)
            self.refresh_calendar()

    def open_selected_folder(self) -> None:
        folder = self.selected_folder.get().strip()
        if folder:
            open_path(Path(folder))

    def settings_from_gui(self) -> ArchiveSettings:
        try:
            max_file_bytes = int(float(self.max_file_mb.get()) * 1_000_000)
        except ValueError:
            raise ValueError("Max File MB must be numeric.")

        try:
            max_total_bytes = int(float(self.max_total_mb.get()) * 1_000_000)
        except ValueError:
            raise ValueError("Max Total MB must be numeric.")

        return ArchiveSettings(
            archive_name=self.archive_name.get().strip(),
            archive_description=self.archive_description.get().strip(),
            include_zip_snapshot=self.include_zip.get(),
            include_hashes=self.include_hashes.get(),
            include_folder_tree=self.include_tree.get(),
            include_diff_report=self.include_diff.get(),
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )

    def create_snapshot_from_gui(self) -> None:
        folder = self.selected_folder.get().strip()

        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        try:
            self.save_settings_from_gui(show_message=False)
            self.status.set("Creating archive snapshot...")
            self.window.update_idletasks()

            result = create_snapshot(folder, settings=self.settings_from_gui())

            self.status.set(
                f"Snapshot complete: {result.export_dir} "
                f"({result.included_count} files, {human_bytes(result.total_included_bytes)})"
            )

            messagebox.showinfo(
                "Snapshot Complete",
                (
                    f"Snapshot folder:\n{result.export_dir}\n\n"
                    f"Included files: {result.included_count}\n"
                    f"Skipped files: {result.skipped_count}\n"
                    f"Included size: {human_bytes(result.total_included_bytes)}"
                ),
            )

            self.refresh_calendar()

        except Exception as exc:
            self.status.set(f"Snapshot failed: {exc}")
            messagebox.showerror("Snapshot Failed", str(exc))

    def save_settings_from_gui(self, show_message: bool = True) -> None:
        try:
            settings = AppSettings(
                selected_archive_folder=self.selected_folder.get().strip(),
                archive_name=self.archive_name.get().strip(),
                archive_description=self.archive_description.get().strip(),
                daily_mode_enabled=self.daily_enabled.get(),
                daily_run_hour=int(self.daily_hour.get()),
                daily_run_minute=int(self.daily_minute.get()),
                include_zip_snapshot=self.include_zip.get(),
                include_hashes=self.include_hashes.get(),
                include_folder_tree=self.include_tree.get(),
                include_diff_report=self.include_diff.get(),
                max_file_mb=float(self.max_file_mb.get()),
                max_total_mb=float(self.max_total_mb.get()),
            )

            save_app_settings(settings)
            self.status.set("Settings saved.")

            if show_message:
                messagebox.showinfo("Settings Saved", "ArchiveTimeline settings saved.")

        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def refresh_calendar(self) -> None:
        for widget in self.calendar_grid.winfo_children():
            widget.destroy()

        self.calendar_buttons.clear()

        month_name = calendar.month_name[self.current_month]
        self.month_label.config(text=f"{month_name} {self.current_year}")

        headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        for col, name in enumerate(headers):
            tk.Label(
                self.calendar_grid,
                text=name,
                font=("Segoe UI", 10, "bold"),
                width=12,
                relief="ridge",
            ).grid(row=0, column=col, sticky="nsew")

        folder = self.selected_folder.get().strip()
        grouped = {}

        if folder:
            try:
                grouped = snapshots_by_date(Path(folder).expanduser().resolve())
            except Exception:
                grouped = {}

        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(self.current_year, self.current_month)

        for row_index, week in enumerate(month_days, start=1):
            for col_index, date_value in enumerate(week):
                date_key = date_value.strftime("%Y-%m-%d")
                in_month = date_value.month == self.current_month
                snapshots = grouped.get(date_key, [])

                label = str(date_value.day)
                if snapshots:
                    label += f"\n● {len(snapshots)}"

                button = tk.Button(
                    self.calendar_grid,
                    text=label,
                    height=4,
                    width=12,
                    relief="raised",
                    bg="#d9f2d9" if snapshots else ("#eeeeee" if in_month else "#f8f8f8"),
                    fg="black" if in_month else "#999999",
                    command=lambda key=date_key: self.select_date(key),
                )
                button.grid(row=row_index, column=col_index, sticky="nsew", padx=1, pady=1)
                self.calendar_buttons.append(button)

        for index in range(7):
            self.calendar_grid.columnconfigure(index, weight=1)

    def select_date(self, date_key: str) -> None:
        folder = self.selected_folder.get().strip()

        if not folder:
            return

        grouped = snapshots_by_date(Path(folder).expanduser().resolve())
        snapshots = grouped.get(date_key, [])

        if not snapshots:
            self.selected_snapshot = None
            self.show_detail(f"Selected Date: {date_key}\n\nNo snapshots found.")
            return

        self.selected_snapshot = snapshots[-1]

        text = (
            f"Selected Date: {date_key}\n\n"
            f"Snapshots on this date: {len(snapshots)}\n\n"
            f"Latest snapshot:\n"
            f"{self.selected_snapshot.snapshot_dir}\n\n"
            f"Created: {self.selected_snapshot.created}\n"
            f"Archive name: {self.selected_snapshot.archive_name}\n"
            f"Included files: {self.selected_snapshot.included_count}\n"
            f"Skipped files: {self.selected_snapshot.skipped_count}\n"
            f"Included size: {human_bytes(self.selected_snapshot.included_bytes)}"
        )

        self.show_detail(text)

    def show_detail(self, text: str) -> None:
        if self.detail_text is None:
            return

        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)

    def open_selected_snapshot(self) -> None:
        if self.selected_snapshot is None:
            messagebox.showinfo("No Snapshot", "Select a date with a snapshot first.")
            return

        open_path(self.selected_snapshot.snapshot_dir)

    def open_file_in_snapshot(self, filename: str) -> None:
        if self.selected_snapshot is None:
            messagebox.showinfo("No Snapshot", "Select a date with a snapshot first.")
            return

        path = self.selected_snapshot.snapshot_dir / filename

        if not path.exists():
            messagebox.showinfo("File Missing", f"File not found:\n{path}")
            return

        open_path(path)

    def previous_month(self) -> None:
        self.current_month -= 1

        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1

        self.refresh_calendar()

    def next_month(self) -> None:
        self.current_month += 1

        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1

        self.refresh_calendar()

    def jump_today(self) -> None:
        import datetime

        today = datetime.datetime.now()
        self.current_year = today.year
        self.current_month = today.month
        self.refresh_calendar()

    def compare_latest_two(self) -> None:
        folder = self.selected_folder.get().strip()

        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        snapshots = discover_snapshots(Path(folder).expanduser().resolve())

        if len(snapshots) < 2:
            messagebox.showinfo("Not Enough Snapshots", "At least two snapshots are required.")
            return

        old_snapshot = snapshots[-2]
        new_snapshot = snapshots[-1]

        try:
            diff = compare_snapshot_dirs(old_snapshot.snapshot_dir, new_snapshot.snapshot_dir)
            text = build_diff_markdown(diff)
            self.compare_text.delete("1.0", tk.END)
            self.compare_text.insert("1.0", text)
        except Exception as exc:
            messagebox.showerror("Compare Failed", str(exc))

    def verify_latest_snapshot(self) -> None:
        folder = self.selected_folder.get().strip()

        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        root = Path(folder).expanduser().resolve()
        snapshots = discover_snapshots(root)

        if not snapshots:
            messagebox.showinfo("No Snapshots", "No snapshots found.")
            return

        latest = snapshots[-1]

        try:
            result = verify_snapshot_against_source(latest.snapshot_dir, root)
            text = build_verify_report(result)
            self.verify_text.delete("1.0", tk.END)
            self.verify_text.insert("1.0", text)
        except Exception as exc:
            messagebox.showerror("Verify Failed", str(exc))

    def daily_check_loop(self) -> None:
        """
        Visible daily mode.

        This only works while the GUI is open.
        It does not install a hidden service.
        """
        try:
            if self.daily_enabled.get():
                import datetime

                now = datetime.datetime.now()
                hour = int(self.daily_hour.get())
                minute = int(self.daily_minute.get())

                state_path = Path.cwd() / "DAILY_ARCHIVE_STATE.json"
                state = {}

                if state_path.exists():
                    try:
                        state = json.loads(state_path.read_text(encoding="utf-8"))
                    except Exception:
                        state = {}

                today_key = now.strftime("%Y-%m-%d")
                last_run = state.get("last_run")

                if last_run != today_key and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
                    folder = self.selected_folder.get().strip()

                    if folder:
                        create_snapshot(folder, settings=self.settings_from_gui())
                        state["last_run"] = today_key
                        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
                        self.status.set(f"Daily archive snapshot created for {today_key}.")
                        self.refresh_calendar()

        except Exception as exc:
            self.status.set(f"Daily archive check failed: {exc}")

        self.window.after(60000, self.daily_check_loop)

    def run(self) -> None:
        self.window.mainloop()


def run_gui() -> None:
    app = ArchiveTimelineGUI()
    app.run()