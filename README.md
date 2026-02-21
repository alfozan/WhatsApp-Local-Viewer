# WhatsApp Backup Viewer

A local, read-only Flask app that opens a WhatsApp backup and lets you browse chats in a WhatsApp Web-like interface.

## Screenshots
<img width="1920" height="1080" alt="viewer_showcase_01_overview_all" src="https://github.com/user-attachments/assets/3cd0c72d-ff97-451d-9224-5fab83ed4ef1" />
<img width="1920" height="1080" alt="viewer_showcase_02_jane_mixed_media_links" src="https://github.com/user-attachments/assets/7cbf9bed-5469-4426-8682-74ad797166ae" />
<img width="1920" height="1080" alt="viewer_showcase_05_john_links_image" src="https://github.com/user-attachments/assets/d057f98f-7d46-41ba-a2b1-4676fd06cce2" />
dark mode
<img width="1920" height="1080" alt="viewer_dark_01_overview_all" src="https://github.com/user-attachments/assets/0fca4fb5-7149-44d4-b9c3-c39252354655" />
<img width="1920" height="1080" alt="viewer_dark_02_jane_media_links" src="https://github.com/user-attachments/assets/5aa643d2-2a98-461a-a2ab-3c467c4d68d2" />
<img width="1920" height="1080" alt="viewer_dark_04_groups_tab" src="https://github.com/user-attachments/assets/7c0e9bc2-4a3c-43c6-adab-fd9e39730571" />
mobile view
<img width="430" height="932" alt="viewer_mobile_dark_02_jane_chat" src="https://github.com/user-attachments/assets/2765b840-6e8b-46c2-a919-1b7f997ce33b" />


## What it supports

- Chat sidebar with tabs:
  - `All` (non-archived)
  - `Groups` (non-archived `@g.us`)
  - `Archived` (all archived chats)
- Search scoped to the active tab
- Infinite scrolling in the chat list
- Message history loading with older-message pagination
- WhatsApp-style chat layout and bubbles
- Group bubble sender names resolved from contacts when possible
- Color-coded sender labels in group chats
- Message links are clickable
- Image thumbnails in chat that open in a larger viewer modal
- Group/contact info modal
- Group members view
- Contact/group avatars with DB + media-path fallback lookup
- System/security membership event rows are filtered from message history
- Light/dark theme follows system preference
- Sidebar resize (desktop)

## Data source

Set the backup directory with `--whatsapp-backup-dir` (or `make run WHATSAPP_BACKUP_DIR=...`).

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
make run WHATSAPP_BACKUP_DIR="/path/to/WhatsApp"
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Development

```bash
make tidy
make lint
```

Code files include short docstrings for key helpers, repository functions, and Flask routes.

## Notes

- Timestamps are shown in local browser time.
- Some profile photos or names can still be missing if the backup itself lacks the mapping or asset.
