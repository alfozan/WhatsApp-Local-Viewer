from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

TAB_CHAT_WHERE_CLAUSES = {
    "all": """
        COALESCE(c.ZARCHIVED, 0) = 0
        AND COALESCE(c.ZSESSIONTYPE, 0) != 3
        AND COALESCE(c.ZCONTACTJID, '') <> ''
        AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
    """,
    "groups": """
        COALESCE(c.ZARCHIVED, 0) = 0
        AND COALESCE(c.ZSESSIONTYPE, 0) != 3
        AND COALESCE(c.ZCONTACTJID, '') <> ''
        AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
        AND COALESCE(c.ZCONTACTJID, '') LIKE '%@g.us'
    """,
    "archived": """
        COALESCE(c.ZARCHIVED, 0) = 1
        AND COALESCE(c.ZSESSIONTYPE, 0) != 3
        AND COALESCE(c.ZCONTACTJID, '') <> ''
        AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
    """,
}

MESSAGE_SEARCH_WHERE_CLAUSES = {
    "all": """
        COALESCE(c.ZSESSIONTYPE, 0) != 3
        AND COALESCE(c.ZCONTACTJID, '') <> ''
        AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
    """,
    "groups": """
        COALESCE(c.ZSESSIONTYPE, 0) != 3
        AND COALESCE(c.ZCONTACTJID, '') <> ''
        AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
        AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
        AND COALESCE(c.ZCONTACTJID, '') LIKE '%@g.us'
    """,
    "archived": TAB_CHAT_WHERE_CLAUSES["archived"],
}


def database_path(connection: sqlite3.Connection) -> Path | None:
    """Return the attached main database path when SQLite exposes one."""
    for row in connection.execute("PRAGMA database_list").fetchall():
        if str(row["name"] or "") != "main":
            continue
        file_value = str(row["file"] or "").strip()
        return Path(file_value) if file_value else None
    return None


def backup_dir(connection: sqlite3.Connection) -> Path | None:
    """Infer the WhatsApp export directory from the chat database connection."""
    main_database_path = database_path(connection)
    if main_database_path is None:
        return None
    return main_database_path.parent


def read_only_connection(database_path: Path) -> sqlite3.Connection:
    """Open a short-lived read-only connection for sibling export databases."""
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def normalize_jid(raw_jid: str | None) -> str:
    """Normalize JIDs used for exact set membership checks."""
    return (raw_jid or "").strip().lower()


def expand_contact_aliases(backup_dir: Path, target_jids: set[str]) -> set[str]:
    """Expand LID/phone JIDs through ContactsV2 aliases."""
    if not target_jids:
        return set()

    contacts_path = backup_dir / "ContactsV2.sqlite"
    if not contacts_path.exists():
        return set()

    aliases: set[str] = set()
    placeholders = ", ".join("?" for _ in target_jids)
    alias_sql = f"""
        SELECT ZLID AS lid_jid, ZWHATSAPPID AS whatsapp_jid
        FROM ZWAADDRESSBOOKCONTACT
        WHERE ZLID IN ({placeholders})
           OR ZWHATSAPPID IN ({placeholders})
    """  # noqa: S608
    try:
        with closing(read_only_connection(contacts_path)) as contacts_connection:
            rows = contacts_connection.execute(alias_sql, [*target_jids, *target_jids]).fetchall()
    except sqlite3.Error:
        return aliases

    for row in rows:
        lid_jid = normalize_jid(row["lid_jid"])
        whatsapp_jid = normalize_jid(row["whatsapp_jid"])
        if lid_jid:
            aliases.add(lid_jid)
        if whatsapp_jid:
            aliases.add(whatsapp_jid)
    return aliases


def expand_chat_session_aliases(connection: sqlite3.Connection, target_jids: set[str]) -> set[str]:
    """Expand JIDs through chat session phone/LID aliases."""
    if not target_jids:
        return set()

    aliases: set[str] = set()
    placeholders = ", ".join("?" for _ in target_jids)
    alias_sql = f"""
        SELECT ZCONTACTJID AS contact_jid, ZCONTACTIDENTIFIER AS contact_identifier
        FROM ZWACHATSESSION
        WHERE ZCONTACTJID IN ({placeholders})
           OR ZCONTACTIDENTIFIER IN ({placeholders})
    """  # noqa: S608
    try:
        rows = connection.execute(alias_sql, [*target_jids, *target_jids]).fetchall()
    except sqlite3.Error:
        return aliases

    for row in rows:
        contact_jid = normalize_jid(row["contact_jid"])
        contact_identifier = normalize_jid(row["contact_identifier"])
        if contact_jid:
            aliases.add(contact_jid)
        if contact_identifier:
            aliases.add(contact_identifier)
    return aliases
