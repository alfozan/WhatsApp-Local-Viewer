from __future__ import annotations

import base64
import binascii
import mimetypes
import sqlite3
from functools import lru_cache
from pathlib import Path

from models import MediaAttachment


def encode_media_token(raw_path: str) -> str:
    """Encode a media path for use in `/media/...` URLs."""
    encoded = base64.urlsafe_b64encode(raw_path.encode("utf-8"))
    return encoded.decode("ascii").rstrip("=")


def decode_media_token(token: str) -> str | None:
    """Decode a media path token from the `/media/...` route."""
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
    except UnicodeDecodeError, binascii.Error:
        return None
    return decoded if decoded else None


def normalize_media_path(raw_path: str | None) -> str:
    """Normalize backup-relative media paths across WhatsApp variants."""
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
    """Return whether `candidate` is inside `base_dir`."""
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        return False
    return True


def _find_with_suffixes(candidate: Path, suffixes: list[str], backup_root: Path) -> Path | None:
    """Try file suffix fallbacks for a media candidate without extension."""
    if candidate.suffix:
        return None
    for suffix in suffixes:
        candidate_with_suffix = candidate.with_suffix(suffix)
        if _is_inside(backup_root, candidate_with_suffix) and candidate_with_suffix.is_file():
            return candidate_with_suffix
    return None


def _resolve_candidate(candidate: Path, suffixes: list[str], backup_root: Path) -> Path | None:
    """Resolve a candidate path directly or by extension fallback."""
    if candidate.is_file():
        return candidate
    return _find_with_suffixes(candidate, suffixes, backup_root)


def resolve_media_path(raw_path: str | None, backup_dir: Path) -> Path | None:
    """Resolve a raw WhatsApp media path to an existing file path."""
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
    """Classify media into `(mime_type, kind)` for UI rendering."""
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
    """Build a `MediaAttachment` payload from a raw media path."""
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
    """Return the local-part of a JID-like value."""
    if not jid:
        return ""
    if "@" not in jid:
        return jid
    return jid.split("@", 1)[0]


def _local_part(raw_jid: str | None) -> str:
    """Normalize and extract local-part text from any JID-like value."""
    if not raw_jid:
        return ""
    value = raw_jid.strip().lower()
    if not value:
        return ""
    if "@" in value:
        return value.split("@", 1)[0]
    return value


def _normalize_profile_jid(raw_jid: str | None) -> str:
    """Normalize profile-picture table JIDs into comparable WhatsApp JIDs."""
    value = (raw_jid or "").strip().lower()
    if not value:
        return ""
    if value.startswith("a_"):
        return value.removeprefix("a_")
    if value.startswith("om_"):
        remainder = value.removeprefix("om_")
        return remainder.split("_", 1)[0] if "_" in remainder else remainder
    return value


def _profile_file_rank(file_path: Path, local_id: str) -> tuple[int, ...]:
    """Extract sortable numeric suffix parts from a profile filename."""
    prefix = f"{local_id}-"
    name = file_path.name
    if not name.startswith(prefix):
        return ()

    stem_parts = file_path.stem.removeprefix(prefix).split("-")
    numeric_parts: list[int] = []
    for part in stem_parts:
        if part.isdigit():
            numeric_parts.append(int(part))
    return tuple(numeric_parts)


@lru_cache(maxsize=8)
def _contact_alias_index(contacts_db_path_value: str) -> dict[str, tuple[str, ...]]:
    """Build mapping of contact ID aliases from the contacts database."""
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


@lru_cache(maxsize=8)
def _contact_jid_alias_index(contacts_db_path_value: str) -> dict[str, tuple[str, ...]]:
    """Build mapping of full JID aliases from the contacts database."""
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
        pair_jids = {_normalize_profile_jid(str(row["lid"])), _normalize_profile_jid(str(row["whatsapp_id"]))}
        pair_jids = {jid for jid in pair_jids if "@" in jid}
        if not pair_jids:
            continue
        pair_locals = {_local_part(jid) for jid in pair_jids}
        for key in {*pair_jids, *pair_locals}:
            if key:
                aliases.setdefault(key, set()).update(pair_jids)

    return {key: tuple(sorted(values)) for key, values in aliases.items() if values}


def _candidate_profile_jids(contact_jid: str | None, contacts_db_path: Path | None) -> list[str]:
    """Return ordered candidate full JIDs for profile-picture lookup."""
    normalized_jid = _normalize_profile_jid(contact_jid)
    if not normalized_jid:
        return []

    candidates: list[str] = [normalized_jid]
    if contacts_db_path:
        alias_index = _contact_jid_alias_index(str(contacts_db_path.resolve()))
        for key in (normalized_jid, _local_part(normalized_jid)):
            for alias_jid in alias_index.get(key, ()):
                if alias_jid and alias_jid not in candidates:
                    candidates.append(alias_jid)
    return candidates


def _candidate_profile_ids(contact_jid: str | None, contacts_db_path: Path | None) -> list[str]:
    """Return ordered candidate profile IDs for a contact JID."""
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
def _profile_jid_index_for_backup(backup_dir_value: str) -> dict[str, str]:
    """Index latest profile path by normalized source JID from ChatStorage."""
    chat_storage_path = Path(backup_dir_value) / "ChatStorage.sqlite"
    if not chat_storage_path.exists():
        return {}

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{chat_storage_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT Z_PK AS row_id, COALESCE(ZJID, '') AS source_jid, COALESCE(ZPATH, '') AS raw_path
            FROM ZWAPROFILEPICTUREITEM
            WHERE COALESCE(ZPATH, '') <> ''
            """
        ).fetchall()
    except sqlite3.DatabaseError:
        return {}
    finally:
        if connection is not None:
            connection.close()

    indexed: dict[str, tuple[int, str]] = {}
    for row in rows:
        source_jid = _normalize_profile_jid(str(row["source_jid"]))
        normalized_path = normalize_media_path(str(row["raw_path"]))
        if not source_jid or "@" not in source_jid:
            continue
        if not normalized_path.startswith("Media/Profile/"):
            continue
        row_id = int(row["row_id"] or 0)
        current = indexed.get(source_jid)
        if current is None or row_id > current[0]:
            indexed[source_jid] = (row_id, normalized_path)

    return {jid: value[1] for jid, value in indexed.items()}


@lru_cache(maxsize=8)
def _group_prefix_ids_for_backup(backup_dir_value: str) -> set[str]:
    """Return numeric prefixes that belong to group JIDs in profile metadata."""
    group_prefixes: set[str] = set()
    for source_jid in _profile_jid_index_for_backup(backup_dir_value):
        if not source_jid.endswith("@g.us"):
            continue
        local = _local_part(source_jid)
        if "-" in local:
            group_prefixes.add(local.split("-", 1)[0])
    return group_prefixes


@lru_cache(maxsize=8)
def _profile_index_for_backup(backup_dir_value: str) -> dict[str, str]:
    """Index latest profile image path by local identifier."""
    profile_dir = Path(backup_dir_value) / "Media" / "Profile"
    if not profile_dir.exists():
        return {}

    indexed: dict[str, tuple[tuple[int, ...], float, str]] = {}
    for file_path in profile_dir.iterdir():
        if not file_path.is_file() or "-" not in file_path.name:
            continue
        local_id = file_path.name.split("-", 1)[0]
        mtime = file_path.stat().st_mtime
        rank = _profile_file_rank(file_path, local_id)
        relative_path = f"Media/Profile/{file_path.name}"
        current = indexed.get(local_id)
        if current is None or (rank, mtime, relative_path) > current:
            indexed[local_id] = (rank, mtime, relative_path)
    return {local_id: value[2] for local_id, value in indexed.items()}


def find_profile_media_for_jid(
    contact_jid: str | None,
    backup_dir: Path,
    contacts_db_path: Path | None = None,
) -> str | None:
    """Find the best profile media path for a contact JID."""
    normalized_jid = _normalize_profile_jid(contact_jid)
    if not normalized_jid:
        return None

    backup_key = str(backup_dir.resolve())
    jid_index = _profile_jid_index_for_backup(backup_key)
    for candidate_jid in _candidate_profile_jids(normalized_jid, contacts_db_path):
        match = jid_index.get(candidate_jid)
        if match:
            return match

    # Last-resort filesystem fallback can collide with group IDs; avoid that for direct numeric JIDs.
    group_prefixes = _group_prefix_ids_for_backup(backup_key)
    is_direct_jid = normalized_jid.endswith(("@s.whatsapp.net", "@c.us"))
    index = _profile_index_for_backup(backup_key)
    for candidate_id in _candidate_profile_ids(normalized_jid, contacts_db_path):
        if is_direct_jid and candidate_id.isdigit() and candidate_id in group_prefixes:
            continue
        match = index.get(candidate_id)
        if match:
            return match
    return None
