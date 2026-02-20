# WhatsApp Backup Viewer

Local read-only Flask app that displays WhatsApp backup chats in a WhatsApp Web-style UI.

## Data source

Default backup path:

`/Users/alfozan/Local/WhatsApp`

You can override it with:

`WHATSAPP_BACKUP_DIR=/path/to/WhatsApp`

The app expects:

- `ChatStorage.sqlite`
- media files under the backup folder (including `Message/Media/...`)

## Run

```bash
make setup
make run
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Sidebar tabs

- `All`: non-archived chats
- `Groups`: non-archived group chats (`@g.us`)
- `Archived`: archived chats (direct + group)

Group chats that are archived appear only in `Archived`.

## Development

After edits:

```bash
make tidy
make lint
```
