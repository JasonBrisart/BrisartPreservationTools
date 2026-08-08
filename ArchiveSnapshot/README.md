# ArchiveSnapshot

**Version 2.0.0 — Architecture Rebuild**

ArchiveSnapshot is a local-first, calendar-based archival snapshot tool for
BrisartPreservationTools. It creates dated preservation snapshots of
important digital folders so future users can understand:

- what existed
- when it existed
- how it was organized
- what changed over time
- whether preserved files can be verified

ArchiveSnapshot is not generic backup software. It is designed for
archival context preservation.

## Core Idea

A backup answers:

> Can I restore the files?

ArchiveSnapshot answers:

> What existed here on this date?

---

## What Changed in v2.0.0

This release is a full architectural rebuild, not a feature update. Every
source file has been renamed and reorganized into a package layout with a
single, clear responsibility per module. Nothing in this rebuild changes
how existing snapshots are stored or read — only how the codebase itself
is organized.

**Every file was renamed.** There is intentionally no file in this release
that shares a name with any file from a previous version, so there is no
ambiguity about which version of a module you are looking at.

**Two legacy files were retired entirely:**

- The old standalone, single-file `ArchiveSnapshot.py` (v1.0.0) — a
  flat, non-package script that predated the calendar/timeline design and
  had become fully superseded by the current engine. It is not needed
  and is not included in this release.
- The old standalone `DailyArchiveBackup.py` script, which depended on
  the file above — its functionality has been ported into
  `automation/daily_snapshot_runner.py`, which now runs on the exact same
  engine as the GUI and CLI. Daily jobs and manual snapshots now produce
  identical results by construction, instead of two parallel
  implementations that could quietly drift apart.

**One entry point instead of several.** Previously there was `run.py`
plus a separate `DailyArchiveBackup.py` script. Both are now unified into
a single [`main.py`](main.py) with subcommands (`snapshot`, `daily`, or no
arguments for the GUI). See [Usage](#usage) below.

**What did *not* change (on purpose):**

- The on-disk snapshot storage folder name (`ARCHIVE_TIMELINE/`) and the
  files generated inside each dated snapshot (`ARCHIVE_SUMMARY.md`,
  `ARCHIVE_MANIFEST.json`, `HASHES.sha256`, `FOLDER_TREE.txt`,
  `ARCHIVE_SETTINGS.json`, `ARCHIVE_FILES.zip`,
  `CHANGES_SINCE_PREVIOUS.md`) are all unchanged. Every snapshot you have
  already created remains fully readable, comparable, and verifiable by
  this version with no migration step.
- The Project Context Helper inbox contract (`SNAPSHOT_ACTIVE/PROJECT_CONTEXT_HELPER/`)
  and the filenames it expects (`PROJECT_CONTEXT.md`, `PROJECT_SUMMARY.txt`,
  `PROJECT_CONTEXT_SETTINGS.json`, `PROJECT_MANIFEST.json`,
  `PROJECT_SNAPSHOT.zip`) are unchanged — those are Project Context
  Helper's own file formats, not ArchiveSnapshot's, so ArchiveSnapshot
  does not rename them.
- The GUI's saved settings will migrate forward automatically. If a
  settings file from an earlier build is found and the current one
  is not, it is read once so your folder and options are not lost.

---

## Architecture

```text
ArchiveSnapshot/
├── main.py                          # single entry point (GUI / CLI / daily)
├── README.md
├── engine/                          # core logic — no GUI, no CLI dependency
│   ├── __init__.py                    # public API re-exports
│   ├── app_info.py                    # app metadata + shared filenames
│   ├── settings.py                    # ArchiveSettings, AppSettings, records
│   ├── folder_scanner.py              # scanning, exclusion rules, folder tree
│   ├── snapshot_writer.py             # writes summary/manifest/hashes/zip
│   ├── change_report.py               # compares two snapshots
│   ├── integrity_check.py             # verifies a snapshot against source
│   ├── timeline_index.py              # discovers/indexes snapshots by date
│   ├── snapshot_builder.py            # orchestrates one full snapshot
│   └── project_context_import.py      # imports a Project Context Helper bundle
├── automation/                      # headless daily automation, no GUI required
│   ├── __init__.py
│   └── daily_snapshot_runner.py       # config-driven daily snapshot jobs
└── ui/                               # presentation layer — one module per tab
    ├── __init__.py                    # public API re-exports (run_gui)
    ├── app.py                         # main window + tab coordination
    ├── app_settings.py                # GUI settings load/save
    ├── path_actions.py                # shared folder picker + file/folder opening
    ├── calendar_tab.py                # Calendar tab
    ├── snapshot_tab.py                # Create Snapshot tab
    ├── comparison_tab.py              # Compare tab
    ├── verification_tab.py            # Verify tab
    ├── settings_tab.py                # Settings tab
    └── about_tab.py                   # About tab
```

**Design rule:** `engine/` never imports from `ui/` or `automation/`.
Both `ui/` and `automation/` call into `engine/` — they never duplicate
its logic. This is what guarantees a snapshot created from the calendar,
from the command line, or from an unattended daily job all look
identical on disk.

### File Reference

| File | Replaces (v1.x) | Responsibility |
| --- | --- | --- |
| [main.py](main.py) | run.py, DailyArchiveBackup.py | Single CLI/GUI/daily entry point |
| [engine/app_info.py](engine/app_info.py) | constants.py | App metadata, shared filenames |
| [engine/settings.py](engine/settings.py) | models.py | Settings + result dataclasses |
| [engine/folder_scanner.py](engine/folder_scanner.py) | scanner.py | Folder walk, exclusions, hashing |
| [engine/snapshot_writer.py](engine/snapshot_writer.py) | exporters.py | Summary/manifest/hashes/ZIP output |
| [engine/change_report.py](engine/change_report.py) | diff_engine.py | Snapshot-to-snapshot diff |
| [engine/integrity_check.py](engine/integrity_check.py) | verifier.py | Snapshot-vs-source verification |
| [engine/timeline_index.py](engine/timeline_index.py) | timeline.py | Snapshot discovery + indexing |
| [engine/snapshot_builder.py](engine/snapshot_builder.py) | snapshot_engine.py | Orchestrates one snapshot |
| [engine/project_context_import.py](engine/project_context_import.py) | project_context.py | Project Context Helper import |
| [automation/daily_snapshot_runner.py](automation/daily_snapshot_runner.py) | DailyArchiveBackup.py | Headless daily snapshot jobs |
| [ui/app.py](ui/app.py) | gui.py | Main window + tab coordination |
| [ui/app_settings.py](ui/app_settings.py) | gui.py | GUI settings load/save |
| [ui/path_actions.py](ui/path_actions.py) | gui.py | Shared folder picker + file/folder opening |
| [ui/calendar_tab.py](ui/calendar_tab.py) | gui.py | Calendar tab |
| [ui/snapshot_tab.py](ui/snapshot_tab.py) | gui.py | Create Snapshot tab |
| [ui/comparison_tab.py](ui/comparison_tab.py) | gui.py | Compare tab |
| [ui/verification_tab.py](ui/verification_tab.py) | gui.py | Verify tab |
| [ui/settings_tab.py](ui/settings_tab.py) | gui.py | Settings tab |
| [ui/about_tab.py](ui/about_tab.py) | gui.py | About tab |
| — *(retired)* | ArchiveSnapshot.py (v1.0.0) | Superseded by engine/; removed |

### Generated Outputs

Each dated snapshot may contain:

- `ARCHIVE_SUMMARY.md` — human-readable overview
- `ARCHIVE_MANIFEST.json` — machine-readable file index, hashes, and settings
- `HASHES.sha256` — SHA256 checksums for every included file
- `FOLDER_TREE.txt` — a readable tree of what was captured
- `ARCHIVE_SETTINGS.json` — the exact settings used for this snapshot
- `ARCHIVE_FILES.zip` — a ZIP of the generated records plus every included file
- `CHANGES_SINCE_PREVIOUS.md` — diff against the previous snapshot, if one exists
- `PROJECT_CONTEXT_HELPER/` — an attached Project Context Helper bundle, if one was provided

### Timeline Layout

Snapshots are stored in a date-based structure inside the archived folder:

```text
<Archived Folder>/
└── ARCHIVE_TIMELINE/
    ├── 2026/
    │   └── 07/
    │       ├── 2026-07-12_064500/
    │       └── 2026-07-13_020000/
    ├── TIMELINE_INDEX.json
    └── TIMELINE_LOG.md
```

### Project Context Helper Import

ArchiveSnapshot does not generate Project Context Helper exports — it
only imports an already-created bundle. To attach one to a snapshot:

1. Run Project Context Helper on the project you want documented.
2. Copy `PROJECT_CONTEXT.md`, `PROJECT_SUMMARY.txt`,
   `PROJECT_CONTEXT_SETTINGS.json`, and `PROJECT_MANIFEST.json` into:
   `<Archive Folder>/SNAPSHOT_ACTIVE/PROJECT_CONTEXT_HELPER/`
3. Create a snapshot as usual (GUI, CLI, or daily job). The bundle is
   copied into the dated snapshot folder and indexed in
   `PROJECT_CONTEXT_INDEX.json`.

## Usage

### GUI

```bash
python main.py
```

Opens the calendar app: browse months, see which days have snapshots,
create a snapshot, compare the two latest snapshots, verify the latest
snapshot against the live folder, and manage settings — including
enabling daily mode while the GUI stays open.

### Command line — single snapshot

```bash
python main.py snapshot "C:\path\to\folder" --name "My Archive"
```

Common flags: `--description`, `--no-zip`, `--no-hashes`, `--no-diff`,
`--no-project-context`, `--max-file-mb`, `--max-total-mb`.

### Headless daily automation

No GUI needs to be open for this — it is meant to run under a scheduled
task, cron job, or process manager you configure yourself.

```bash
# 1. Create an example config
python main.py daily --init-config --config DAILY_SNAPSHOT_CONFIG.json

# 2. Edit the config: set source_folder, enabled: true, and any options
#    per job (see automation/daily_snapshot_runner.py for all fields)

# 3a. Run any due jobs once and exit (good for a scheduled task/cron entry)
python main.py daily --once --config DAILY_SNAPSHOT_CONFIG.json

# 3b. Or run a long-lived watcher that checks once per day at the
#     configured run_hour/run_minute
python main.py daily --watch --config DAILY_SNAPSHOT_CONFIG.json
```

Add `--force` to `--once` to re-run jobs that already ran today.

## Verification & Comparison

- **Compare** — `engine.change_report.compare_snapshot_dirs` diffs two
  snapshots' manifests and reports added/removed/modified/unchanged
  files. Available from the GUI's Compare tab.
- **Verify** — `engine.integrity_check.verify_snapshot_against_source`
  re-hashes the live source folder and checks it against a snapshot's
  recorded hashes and sizes, flagging anything changed or missing since
  the snapshot was taken. Available from the GUI's Verify tab.

Created by Jason Brisart
Part of BrisartPreservationTools
