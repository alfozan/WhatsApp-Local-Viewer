# WhatsApp Backup Viewer

A local, read-only Flask app that opens a copied WhatsApp backup and lets you browse chats in a WhatsApp Web-like interface.

## What it supports

- Chat sidebar with tabs:
  - `All` (non-archived)
  - `Groups` (non-archived `@g.us`)
  - `Archived` (all archived chats)
- Search scoped to the active tab
- Infinite scrolling in the chat list
- Message history loading with older-message pagination
- WhatsApp-style chat layout and bubbles
- Message links are clickable
- Image thumbnails in chat that open in a larger viewer modal
- Group/contact info modal
- Group members view
- Contact/group avatars with DB + media-path fallback lookup
- Light/dark theme follows system preference
- Sidebar resize (desktop)

## Data source

Set the backup directory with `--backup-dir` (or `make run BACKUP_DIR=...`).

Expected files:

- `ChatStorage.sqlite` (required)
- `ContactsV2.sqlite` (used for contact/member name enrichment when available)
- media files inside the backup directory (for example `Message/Media/...`, `Media/Profile/...`)

## Read-only guarantee

This app only performs read operations against the backup:

- SQLite is opened with `mode=ro`
- No write/update/delete SQL is executed
- No files are modified inside your backup folder

## Run

```bash
make setup
make run BACKUP_DIR="/path/to/WhatsApp"
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Development

```bash
make tidy
make lint
```

## Notes

- Timestamps are shown in local browser time.
- Some profile photos or names can still be missing if the backup itself lacks the mapping or asset.
