from __future__ import annotations

import base64
import binascii
import mimetypes
import sqlite3
from functools import lru_cache
from pathlib import Path

from .models import MediaAttachment


def encode_media_token(raw_path: str) -> str:
    encoded = base64.urlsafe_b64encode(raw_path.encode("utf-8"))
    return encoded.decode("ascii").rstrip("=")


def decode_media_token(token: str) -> str | None:
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
    except UnicodeDecodeError, binascii.Error:
        return None
    return decoded if decoded else None


def normalize_media_path(raw_path: str | None) -> str:
    if not raw_path:
        return ""
    cleaned = raw_path.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("/Media/Profile/"):
        return cleaned.removeprefix("/")
    if cleaned.startswith("Media/Profile/"):
        return cleaned
    if cleaned.startswith("/Media/"):
        return f"Message{cleaned}"
    if cleaned.startswith("Media/"):
        return f"Message/{cleaned}"
    return cleaned


def _is_inside(base_dir: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        return False
    return True


def _find_with_suffixes(candidate: Path, suffixes: list[str], backup_root: Path) -> Path | None:
    if candidate.suffix:
        return None
    for suffix in suffixes:
        candidate_with_suffix = candidate.with_suffix(suffix)
        if _is_inside(backup_root, candidate_with_suffix) and candidate_with_suffix.is_file():
            return candidate_with_suffix
    return None


def _resolve_candidate(candidate: Path, suffixes: list[str], backup_root: Path) -> Path | None:
    if candidate.is_file():
        return candidate
    return _find_with_suffixes(candidate, suffixes, backup_root)


def resolve_media_path(raw_path: str | None, backup_dir: Path) -> Path | None:
    normalized = normalize_media_path(raw_path)
    if not normalized:
        return None

    normalized_path = Path(normalized)
    if normalized_path.is_absolute():
        candidate = normalized_path
    else:
        candidate = backup_dir / normalized_path

    candidate = candidate.resolve()
    backup_root = backup_dir.resolve()
    if not _is_inside(backup_root, candidate):
        return None

    suffixes = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".m4a", ".opus", ".mp3", ".thumb"]
    resolved_candidate = _resolve_candidate(candidate, suffixes, backup_root)
    if resolved_candidate is not None:
        return resolved_candidate

    if normalized.startswith("Message/Media/"):
        alt_path = (backup_dir / normalized.removeprefix("Message/")).resolve()
        if not _is_inside(backup_root, alt_path):
            return None
        resolved_alt = _resolve_candidate(alt_path, suffixes, backup_root)
        if resolved_alt is not None:
            return resolved_alt

    return None


def classify_media(file_path: Path | None) -> tuple[str, str]:
    if file_path and file_path.suffix.lower() == ".thumb":
        return "image/jpeg", "image"
    mime_type, _ = mimetypes.guess_type(file_path.name if file_path else "")
    normalized_mime = mime_type or "application/octet-stream"
    if normalized_mime.startswith("image/"):
        return normalized_mime, "image"
    if normalized_mime.startswith("video/"):
        return normalized_mime, "video"
    if normalized_mime.startswith("audio/"):
        return normalized_mime, "audio"
    return normalized_mime, "document"


def build_media_attachment(raw_path: str, media_url: str, backup_dir: Path) -> MediaAttachment:
    resolved = resolve_media_path(raw_path, backup_dir)
    mime_type, kind = classify_media(resolved)
    file_name = resolved.name if resolved else Path(raw_path).name
    return MediaAttachment(
        raw_path=raw_path,
        url=media_url,
        mime_type=mime_type,
        kind=kind,
        file_name=file_name,
        available=resolved is not None,
    )


def _jid_local_part(jid: str | None) -> str:
    if not jid:
        return ""
    if "@" not in jid:
        return jid
    return jid.split("@", 1)[0]


def _local_part(raw_jid: str | None) -> str:
    if not raw_jid:
        return ""
    value = raw_jid.strip().lower()
    if not value:
        return ""
    if "@" in value:
        return value.split("@", 1)[0]
    return value


@lru_cache(maxsize=8)
def _contact_alias_index(contacts_db_path_value: str) -> dict[str, tuple[str, ...]]:
    contacts_db_path = Path(contacts_db_path_value)
    if not contacts_db_path.exists():
        return {}

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{contacts_db_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT COALESCE(ZLID, '') AS lid, COALESCE(ZWHATSAPPID, '') AS whatsapp_id
            FROM ZWAADDRESSBOOKCONTACT
            WHERE COALESCE(ZLID, '') <> '' OR COALESCE(ZWHATSAPPID, '') <> ''
            """
        ).fetchall()
    except sqlite3.DatabaseError:
        return {}
    finally:
        if connection is not None:
            connection.close()

    aliases: dict[str, set[str]] = {}
    for row in rows:
        pair_ids = {_local_part(str(row["lid"])), _local_part(str(row["whatsapp_id"]))}
        pair_ids.discard("")
        if not pair_ids:
            continue
        for key in pair_ids:
            aliases.setdefault(key, set()).update(pair_ids)

    return {key: tuple(sorted(values)) for key, values in aliases.items() if values}


def _candidate_profile_ids(contact_jid: str | None, contacts_db_path: Path | None) -> list[str]:
    local_id = _jid_local_part(contact_jid)
    if not local_id:
        return []

    candidate_ids: list[str] = [local_id]
    if contacts_db_path:
        alias_index = _contact_alias_index(str(contacts_db_path.resolve()))
        for alias_id in alias_index.get(local_id.lower(), ()):
            if alias_id and alias_id not in candidate_ids:
                candidate_ids.append(alias_id)
    return candidate_ids


@lru_cache(maxsize=8)
def _profile_index_for_backup(backup_dir_value: str) -> dict[str, str]:
    profile_dir = Path(backup_dir_value) / "Media" / "Profile"
    if not profile_dir.exists():
        return {}

    indexed: dict[str, tuple[float, str]] = {}
    for file_path in profile_dir.iterdir():
        if not file_path.is_file() or "-" not in file_path.name:
            continue
        local_id = file_path.name.split("-", 1)[0]
        mtime = file_path.stat().st_mtime
        relative_path = f"Media/Profile/{file_path.name}"
        current = indexed.get(local_id)
        if current is None or mtime > current[0]:
            indexed[local_id] = (mtime, relative_path)
    return {local_id: value[1] for local_id, value in indexed.items()}


def find_profile_media_for_jid(
    contact_jid: str | None,
    backup_dir: Path,
    contacts_db_path: Path | None = None,
) -> str | None:
    index = _profile_index_for_backup(str(backup_dir.resolve()))
    for candidate_id in _candidate_profile_ids(contact_jid, contacts_db_path):
        match = index.get(candidate_id)
        if match:
            return match
    return None
