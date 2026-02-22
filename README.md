# WhatsApp Local Viewer

Browse your WhatsApp chats from the macOS app directly in your browser — no uploads, no cloud, no third-party servers. Everything runs locally on your machine.

It reads WhatsApp's SQLite databases in **read-only mode** and serves a WhatsApp Web-like interface at `localhost`. Your data never leaves your device.

---

## 📸 Screenshots

<table>
  <tr>
    <th>Light</th>
    <th>Dark</th>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/3cd0c72d-ff97-451d-9224-5fab83ed4ef1" /></td>
    <td><img src="https://github.com/user-attachments/assets/0fca4fb5-7149-44d4-b9c3-c39252354655" /></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/7cbf9bed-5469-4426-8682-74ad797166ae" /></td>
    <td><img src="https://github.com/user-attachments/assets/5aa643d2-2a98-461a-a2ab-3c467c4d68d2" /></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/d057f98f-7d46-41ba-a2b1-4676fd06cce2" /></td>
    <td><img src="https://github.com/user-attachments/assets/7c0e9bc2-4a3c-43c6-adab-fd9e39730571" /></td>
  </tr>
</table>

Mobile

<img width="430" height="932" src="https://github.com/user-attachments/assets/2765b840-6e8b-46c2-a919-1b7f997ce33b" />

---

## ✨ Features

- Browse chats across `All`, `Groups`, and `Archived` tabs with search and infinite scroll
- View messages with full media support: images, videos, audio, documents, polls, and contact cards
- Replied/quoted messages, @mentions, call events, and group sender labels all rendered correctly
- Contact and group info modals with member lists and avatars
- 🌙 Light/dark theme (follows system preference), responsive on mobile, resizable sidebar on desktop

---

## 📂 Data source

Point `--whatsapp-dir` at any directory that contains a `ChatStorage.sqlite` file. This can be:

- **macOS app** — the live data directory used by WhatsApp for Mac (no copying needed):
  ```
  ~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared
  ```
- **iOS backup** — extracted from an iPhone backup (e.g. via iMazing or similar):
  ```
  ~/Desktop/WhatsApp-iOS-Export
  ```
- **Android backup** — extracted from an Android backup or file transfer:
  ```
  ~/Desktop/WhatsApp-Android-Export
  ```

The app looks for these files inside that directory:

| File | Purpose |
|------|---------|
| `ChatStorage.sqlite` | All chats and messages (required) |
| `ContactsV2.sqlite` | Resolves phone numbers to display names |
| `Message/Media/…`, `Media/Profile/…` | Images, videos, and avatars |

---

## 🔒 Read-only guarantee

This app only reads your data — it never modifies anything:

- SQLite is opened with `mode=ro`
- No `INSERT`, `UPDATE`, or `DELETE` queries are executed
- No files in your data directory are modified
- All processing happens locally; nothing is sent over the network

---

## 🚀 Run

**1. Install dependencies**

```bash
make setup
```

**2. Start the viewer**

```bash
uv run app.py
```

**3. Open in your browser**

```
http://127.0.0.1:5000
```
