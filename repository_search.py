from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from models import MessageSearchResult
from repository_common import (
    MESSAGE_SEARCH_WHERE_CLAUSES,
    TAB_CHAT_WHERE_CLAUSES,
    backup_dir,
    expand_chat_session_aliases,
    expand_contact_aliases,
    normalize_jid,
    read_only_connection,
)
from utils import coredata_to_datetime

MESSAGE_SEARCH_RESULTS_PER_CHAT = 2
MESSAGE_SEARCH_INDEX_MAX_DATES = 900


def _normalize_search_digits(raw_value: str) -> str:
    """Convert Unicode decimal digits to ASCII while leaving other text intact."""
    normalized_characters: list[str] = []
    for character in raw_value:
        try:
            digit_value = unicodedata.decimal(character)
        except TypeError, ValueError:
            normalized_characters.append(character)
            continue
        normalized_characters.append(str(digit_value))
    return "".join(normalized_characters)


def search_query_variants(query: str | None) -> list[str]:
    """Return text and phone-friendly variants for a chat search query."""
    raw_query = (query or "").strip()
    if not raw_query:
        return []

    normalized_query = _normalize_search_digits(raw_query)
    compact_digits = "".join(character for character in normalized_query if character.isascii() and character.isdigit())
    variants: list[str] = []
    for variant in (raw_query, normalized_query, compact_digits):
        if variant and variant not in variants:
            variants.append(variant)
    return variants


def primary_search_query(query: str) -> str:
    """Return the normalized query used by the main chat-session LIKE query."""
    variants = search_query_variants(query)
    if len(variants) >= 2:
        return variants[1]
    return variants[0] if variants else query


def _search_like_values(query_variants: list[str]) -> list[str]:
    """Return SQL LIKE values for non-empty search variants."""
    return [f"%{variant}%" for variant in query_variants if variant]


def _like_conditions(columns: tuple[str, ...], like_values: list[str]) -> tuple[str, list[str]]:
    """Build a constant-column LIKE clause and matching params."""
    conditions = []
    params = []
    for column_name in columns:
        for like_value in like_values:
            conditions.append(f"COALESCE({column_name}, '') LIKE ?")
            params.append(like_value)
    return " OR ".join(conditions), params


def _phone_jid_alias(raw_phone_number: str | None) -> str:
    """Return an `@s.whatsapp.net` alias for a phone-like value."""
    phone_digits = "".join(
        character for character in str(raw_phone_number or "") if character.isascii() and character.isdigit()
    )
    return f"{phone_digits}@s.whatsapp.net" if phone_digits else ""


def _search_contacts_aliases(contacts_path: Path, like_values: list[str]) -> set[str]:
    """Return matching JID aliases from ContactsV2."""
    if not contacts_path.exists():
        return set()

    contact_columns = (
        "ZWHATSAPPID",
        "ZLID",
        "ZFULLNAME",
        "ZGIVENNAME",
        "ZPHONENUMBER",
        "ZLOCALIZEDPHONENUMBER",
    )
    where_clause, params = _like_conditions(contact_columns, like_values)
    contact_sql = f"""
        SELECT ZWHATSAPPID AS whatsapp_jid, ZLID AS lid_jid, ZPHONENUMBER AS phone_number
        FROM ZWAADDRESSBOOKCONTACT
        WHERE {where_clause}
    """  # noqa: S608
    try:
        with closing(read_only_connection(contacts_path)) as contacts_connection:
            rows = contacts_connection.execute(contact_sql, params).fetchall()
    except sqlite3.Error:
        return set()

    aliases: set[str] = set()
    for row in rows:
        aliases.update(
            alias
            for alias in (
                normalize_jid(row["whatsapp_jid"]),
                normalize_jid(row["lid_jid"]),
                _phone_jid_alias(row["phone_number"]),
            )
            if alias
        )
    return aliases


def _search_lid_aliases(lid_path: Path, like_values: list[str]) -> set[str]:
    """Return matching JID aliases from LID account rows."""
    if not lid_path.exists():
        return set()

    where_clause, params = _like_conditions(("ZIDENTIFIER", "ZPHONENUMBER", "ZDISPLAYNAME", "ZUSERNAME"), like_values)
    lid_sql = f"""
        SELECT ZIDENTIFIER AS lid_jid, ZPHONENUMBER AS phone_number
        FROM ZWAZACCOUNT
        WHERE {where_clause}
    """  # noqa: S608
    try:
        with closing(read_only_connection(lid_path)) as lid_connection:
            rows = lid_connection.execute(lid_sql, params).fetchall()
    except sqlite3.Error:
        return set()

    aliases: set[str] = set()
    for row in rows:
        aliases.update(
            alias for alias in (normalize_jid(row["lid_jid"]), _phone_jid_alias(row["phone_number"])) if alias
        )
    return aliases


def _search_contact_aliases(backup_dir: Path, query_variants: list[str]) -> set[str]:
    """Return JID aliases from ContactsV2 and LID rows matching a search query."""
    like_values = _search_like_values(query_variants)
    if not like_values:
        return set()

    aliases = _search_contacts_aliases(backup_dir / "ContactsV2.sqlite", like_values)
    aliases.update(_search_lid_aliases(backup_dir / "LID.sqlite", like_values))
    return aliases


def _chat_ids_for_aliases(
    connection: sqlite3.Connection,
    tab: str,
    aliases: set[str],
) -> list[int]:
    """Return chat ids matching any known JID/identifier alias."""
    if not aliases:
        return []

    placeholders = ", ".join("?" for _ in aliases)
    where_clause = TAB_CHAT_WHERE_CLAUSES[tab]
    alias_sql = f"""
        SELECT c.Z_PK AS chat_id
        FROM ZWACHATSESSION c
        WHERE {where_clause}
          AND (
              c.ZCONTACTJID IN ({placeholders})
              OR c.ZCONTACTIDENTIFIER IN ({placeholders})
          )
    """  # noqa: S608
    rows = connection.execute(alias_sql, [*aliases, *aliases]).fetchall()
    return [int(row["chat_id"]) for row in rows]


def chat_ids_matching_contact_search(
    connection: sqlite3.Connection,
    tab: str,
    query_variants: list[str],
) -> list[int]:
    """Return chat ids whose contact aliases match a search query."""
    export_dir = backup_dir(connection)
    if export_dir is None:
        return []

    aliases = _search_contact_aliases(export_dir, query_variants)
    aliases.update(expand_contact_aliases(export_dir, aliases))
    aliases.update(expand_chat_session_aliases(connection, aliases))
    return _chat_ids_for_aliases(connection, tab, aliases)


def _is_arabic_letter(character: str) -> bool:
    """Return whether a character is an Arabic-script letter."""
    return "\u0600" <= character <= "\u06ff" and character.isalpha()


def _has_arabic_letter(value: str) -> bool:
    """Return whether a string contains any Arabic-script letter."""
    return any(_is_arabic_letter(character) for character in value)


def search_index_text_matches_query(index_text: str, query_variants: list[str]) -> bool:
    """Return whether indexed search text matches normalized query variants."""
    normalized_index_text = _normalize_search_digits(index_text)
    tokens = [token for token in normalized_index_text.split() if token]
    if not tokens:
        return False

    for query_variant in query_variants:
        normalized_variant = _normalize_search_digits(query_variant).strip()
        if not normalized_variant:
            continue
        terms = [term for term in normalized_variant.split() if term]
        if not terms:
            continue
        if any(_has_arabic_letter(term) for term in terms):
            if all(term in tokens for term in terms):
                return True
            continue
        if normalized_variant in normalized_index_text:
            return True
    return False


def _message_search_index_dates(
    connection: sqlite3.Connection,
    query_variants: list[str],
) -> tuple[list[float], bool]:
    """Return matching normal-message dates from WhatsApp's search index."""
    export_dir = backup_dir(connection)
    if export_dir is None:
        return [], False

    search_index_path = export_dir / "fts" / "ChatSearchV5f.sqlite"
    if not search_index_path.exists():
        return [], False

    like_values = _search_like_values(query_variants)
    if not like_values:
        return [], True

    index_where_clause, params = _like_conditions(("dc.c0text",), like_values)
    index_sql = f"""
        SELECT md.date AS message_date, COALESCE(dc.c0text, '') AS index_text
        FROM docs_content dc
        JOIN metadata md ON md.docID = dc.docid
        WHERE COALESCE(dc.c3documentType, '') = ''
          AND ({index_where_clause})
        ORDER BY md.date DESC, dc.docid DESC
        LIMIT ?
    """  # noqa: S608
    try:
        with closing(read_only_connection(search_index_path)) as search_connection:
            rows = search_connection.execute(index_sql, [*params, MESSAGE_SEARCH_INDEX_MAX_DATES]).fetchall()
    except sqlite3.Error:
        return [], False

    return [
        float(row["message_date"])
        for row in rows
        if row["message_date"] is not None
        and search_index_text_matches_query(str(row["index_text"] or ""), query_variants)
    ], True


def _to_message_search_result(row: sqlite3.Row) -> MessageSearchResult:
    """Convert a message search SQL row into a serializable result."""
    contact_jid = str(row["contact_jid"] or "")
    is_group = contact_jid.endswith("@g.us")
    sender_name = "You" if bool(row["is_from_me"] or 0) else str(row["sender_name"] or "")
    if not is_group and not bool(row["is_from_me"] or 0):
        sender_name = ""
    return MessageSearchResult(
        chat_id=int(row["chat_id"]),
        chat_name=str(row["chat_name"] or contact_jid or "Unknown chat"),
        contact_jid=contact_jid,
        message_id=int(row["message_id"]),
        message_date=coredata_to_datetime(row["message_date"]),
        snippet=str(row["snippet"] or ""),
        sender_name=sender_name,
        is_group=is_group,
    )


def message_search_results(
    connection: sqlite3.Connection,
    tab: str,
    query_variants: list[str],
    limit: int,
    offset: int,
) -> list[MessageSearchResult]:
    """Return message-level search results matching WhatsApp's search list."""
    like_values = _search_like_values(query_variants)
    if not like_values:
        return []

    where_clause = MESSAGE_SEARCH_WHERE_CLAUSES[tab]
    index_dates, has_search_index = _message_search_index_dates(connection, query_variants)
    if has_search_index and not index_dates:
        return []

    if has_search_index:
        date_placeholders = ", ".join("?" for _ in index_dates)
        message_where_clause = f"m.ZMESSAGEDATE IN ({date_placeholders})"
        params: list[object] = []
        params.extend(index_dates)
    else:
        message_where_clause, raw_params = _like_conditions(("m.ZTEXT",), like_values)
        params = raw_params

    search_sql = f"""
        WITH matched_messages AS (
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            m.Z_PK AS message_id,
            m.ZMESSAGEDATE AS message_date,
            COALESCE(m.ZTEXT, '') AS snippet,
            COALESCE(m.ZISFROMME, 0) AS is_from_me,
            COALESCE(
                NULLIF(gm.ZCONTACTNAME, ''),
                NULLIF(gm.ZFIRSTNAME, ''),
                NULLIF(
                    (
                        SELECT p.ZPUSHNAME
                        FROM ZWAPROFILEPUSHNAME p
                        WHERE p.ZJID = gm.ZMEMBERJID
                          AND COALESCE(p.ZPUSHNAME, '') <> ''
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                ''
            ) AS sender_name,
            ROW_NUMBER() OVER (
                PARTITION BY c.Z_PK
                ORDER BY m.ZMESSAGEDATE DESC, m.Z_PK DESC
            ) AS chat_hit_rank
        FROM ZWAMESSAGE m
        JOIN ZWACHATSESSION c ON c.Z_PK = m.ZCHATSESSION
        LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
        WHERE {where_clause}
          AND COALESCE(m.ZTEXT, '') <> ''
          AND COALESCE(m.ZMESSAGETYPE, 0) NOT IN (6, 10)
          AND ({message_where_clause})
        )
        SELECT
            chat_id,
            chat_name,
            contact_jid,
            message_id,
            message_date,
            snippet,
            is_from_me,
            sender_name
        FROM matched_messages
        WHERE chat_hit_rank <= ?
        ORDER BY message_date DESC, message_id DESC
        LIMIT ? OFFSET ?
    """  # noqa: S608
    rows = connection.execute(search_sql, [*params, MESSAGE_SEARCH_RESULTS_PER_CHAT, limit, offset]).fetchall()
    return [_to_message_search_result(row) for row in rows]
