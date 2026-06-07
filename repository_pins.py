from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from models import ChatSummary
from repository_common import (
    TAB_CHAT_WHERE_CLAUSES,
    backup_dir,
    expand_chat_session_aliases,
    expand_contact_aliases,
    normalize_jid,
    read_only_connection,
)

PinRecord = tuple[tuple[int, int, int], int, bytes | None]


def _read_varint(raw_value: bytes, position: int) -> tuple[int | None, int]:
    """Read a protobuf varint from `raw_value` starting at `position`."""
    value = 0
    shift = 0
    while position < len(raw_value):
        byte_value = raw_value[position]
        position += 1
        value |= (byte_value & 0x7F) << shift
        if (byte_value & 0x80) == 0:
            return value, position
        shift += 7
        if shift > 63:
            break
    return None, position


def _skip_protobuf_field(raw_value: bytes, position: int, wire_type: int) -> int | None:
    """Return the next protobuf field position, or `None` if parsing fails."""
    if wire_type == 0:
        value, position = _read_varint(raw_value, position)
        return position if value is not None else None
    if wire_type == 1:
        next_position = position + 8
        return next_position if next_position <= len(raw_value) else None
    if wire_type == 2:
        length, position = _read_varint(raw_value, position)
        if length is None:
            return None
        next_position = position + length
        return next_position if next_position <= len(raw_value) else None
    if wire_type == 5:
        next_position = position + 4
        return next_position if next_position <= len(raw_value) else None
    return None


def _app_state_pin_timestamp(raw_value: bytes | None) -> int:
    """Read the AppState pin mutation timestamp from field 1 when present."""
    if not raw_value:
        return 0
    tag, position = _read_varint(raw_value, 0)
    if tag != 8:
        return 0
    timestamp, _position = _read_varint(raw_value, position)
    return timestamp or 0


def _app_state_pin_value(raw_value: bytes | None) -> bool | None:
    """Decode the pinned boolean from a `pin_v1` AppState payload."""
    if not raw_value:
        return None

    position = 0
    while position < len(raw_value):
        tag, position = _read_varint(raw_value, position)
        if tag is None:
            return None

        field_number = tag >> 3
        wire_type = tag & 7
        if field_number == 5 and wire_type == 2:
            length, position = _read_varint(raw_value, position)
            if length is None or position + length > len(raw_value):
                return None
            nested_value = raw_value[position : position + length]
            nested_tag, nested_position = _read_varint(nested_value, 0)
            if nested_tag != 8:
                return None
            pinned_value, _nested_position = _read_varint(nested_value, nested_position)
            return bool(pinned_value)

        next_position = _skip_protobuf_field(raw_value, position, wire_type)
        if next_position is None:
            return None
        position = next_position

    return None


def _app_state_database_paths(backup_dir: Path) -> list[Path]:
    """Return AppState databases available from the configured WhatsApp directory."""
    app_state_dir = backup_dir / "AppState"
    database_paths: list[Path] = []
    seen_paths: set[str] = set()
    if not app_state_dir.exists():
        return database_paths
    for database_path in sorted(app_state_dir.glob("*/AppState.sqlite")):
        path_key = str(database_path.resolve())
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        database_paths.append(database_path)
    return database_paths


def _app_state_pin_rows(database_path: Path) -> tuple[int, list[sqlite3.Row]]:
    """Read raw `pin_v1` rows and database mtime from one AppState DB."""
    try:
        database_mtime = database_path.stat().st_mtime_ns
    except OSError:
        database_mtime = 0

    try:
        with closing(read_only_connection(database_path)) as app_state_connection:
            rows = app_state_connection.execute(
                """
                SELECT
                    Z_PK AS record_id,
                    ZTARGETID AS target_id,
                    COALESCE(ZSTATE, 0) AS state_value,
                    ZVALUE AS value
                FROM ZAPPSTATECONFIRMEDMUTATIONENTITY
                WHERE ZACTIONNAME = 'pin_v1'
                  AND COALESCE(ZTARGETID, '') <> ''
                """
            ).fetchall()
    except sqlite3.Error:
        return database_mtime, []
    return database_mtime, rows


def _read_app_state_pin_targets(backup_dir: Path) -> tuple[set[str], bool]:
    """Read pinned chat targets from AppState `pin_v1` records."""
    latest_records: dict[str, PinRecord] = {}
    found_pin_records = False
    for database_path in _app_state_database_paths(backup_dir):
        database_mtime, rows = _app_state_pin_rows(database_path)

        for row in rows:
            target_id = normalize_jid(row["target_id"])
            if not target_id:
                continue
            found_pin_records = True
            record_id = int(row["record_id"] or 0)
            state_value = int(row["state_value"] or 0)
            raw_value = bytes(row["value"]) if row["value"] is not None else None
            sort_key = (_app_state_pin_timestamp(raw_value), database_mtime, record_id)
            previous = latest_records.get(target_id)
            if previous is None or sort_key > previous[0]:
                latest_records[target_id] = (sort_key, state_value, raw_value)

    pinned_targets: set[str] = set()
    state_active_targets: set[str] = set()
    found_payload_pin_values = False
    for target_id, (_sort_key, state_value, raw_value) in latest_records.items():
        if state_value != 1:
            continue
        state_active_targets.add(target_id)
        pinned_value = _app_state_pin_value(raw_value)
        if pinned_value is None:
            continue
        found_payload_pin_values = True
        if pinned_value:
            pinned_targets.add(target_id)

    if found_payload_pin_values:
        return pinned_targets, found_pin_records
    return state_active_targets, found_pin_records


def pinned_jids_from_export(connection: sqlite3.Connection) -> tuple[set[str], bool]:
    """Return app-state pinned JIDs and whether app-state pin data was present."""
    export_dir = backup_dir(connection)
    if export_dir is None:
        return set(), False

    pinned_jids, has_app_state_pin_data = _read_app_state_pin_targets(export_dir)
    if not has_app_state_pin_data:
        return set(), False

    expanded_jids = set(pinned_jids)
    expanded_jids.update(expand_contact_aliases(export_dir, pinned_jids))
    expanded_jids.update(expand_chat_session_aliases(connection, expanded_jids))
    return expanded_jids, True


def apply_export_pins(
    chats: list[ChatSummary],
    pinned_jids: set[str],
    has_app_state_pin_data: bool,
) -> list[ChatSummary]:
    """Overlay chat pin state from app-state data when available."""
    if not has_app_state_pin_data:
        return chats

    updated: list[ChatSummary] = []
    for chat in chats:
        updated.append(replace(chat, is_pinned=normalize_jid(chat.contact_jid) in pinned_jids))
    return updated


def pinned_chat_ids_for_tab(
    connection: sqlite3.Connection,
    tab: str,
    pinned_jids: set[str],
    query: str | None,
) -> list[int]:
    """Return pinned chat ids that match the active tab/search filters."""
    if not pinned_jids:
        return []

    placeholders = ", ".join("?" for _ in pinned_jids)
    where_clause = TAB_CHAT_WHERE_CLAUSES[tab]
    params: list[object] = [*pinned_jids]
    search_clause = ""
    if query:
        like_value = f"%{query}%"
        search_clause = """
          AND (
              COALESCE(c.ZPARTNERNAME, '') LIKE ?
              OR COALESCE(c.ZCONTACTJID, '') LIKE ?
              OR COALESCE(c.ZLASTMESSAGETEXT, '') LIKE ?
          )
        """
        params.extend([like_value, like_value, like_value])

    pinned_sql = f"""
        SELECT c.Z_PK AS chat_id
        FROM ZWACHATSESSION c
        WHERE {where_clause}
          AND c.ZCONTACTJID IN ({placeholders})
          {search_clause}
    """  # noqa: S608
    rows = connection.execute(pinned_sql, params).fetchall()
    return [int(row["chat_id"]) for row in rows]
