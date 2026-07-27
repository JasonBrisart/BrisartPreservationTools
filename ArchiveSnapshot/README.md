# ArchiveTimeline

ArchiveTimeline is a local-first calendar-based archival timeline tool for BrisartPreservationTools.

It creates dated preservation snapshots of important digital folders so future users can understand:

- what existed
- when it existed
- how it was organized
- what changed over time
- whether preserved files can be verified

ArchiveTimeline is not generic backup software.

It is designed for archival context preservation.

## Core Idea

A backup answers:

> Can I restore the files?

ArchiveTimeline answers:

> What existed here on this date?

## Generated Outputs

Each archive snapshot may generate:

- `ARCHIVE_SUMMARY.md`
- `ARCHIVE_MANIFEST.json`
- `HASHES.sha256`
- `FOLDER_TREE.txt`
- `ARCHIVE_SETTINGS.json`
- `ARCHIVE_FILES.zip`
- `CHANGES_SINCE_PREVIOUS.md`

## Timeline Layout

Snapshots are stored in a date-based structure:

```text
ARCHIVE_TIMELINE/
├── 2026/
│   └── 07/
│       ├── 2026-07-12_064500/
│       └── 2026-07-13_020000/
├── TIMELINE_INDEX.json
└── TIMELINE_LOG.md
