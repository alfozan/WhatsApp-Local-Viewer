from __future__ import annotations

import sqlite3
from typing import Any

from .models import ChatSummary, MessageItem
from .utils import coredata_to_datetime, decode_cursor, encode_cursor

VALID_TABS = {"all", "groups", "archived"}

TAB_COUNT_QUERIES = {
    "all": (
        "SELECT COUNT(*) AS count_value FROM ZWACHATSESSION c "
        "WHERE COALESCE(c.ZARCHIVED, 0) = 0 "
        "AND COALESCE(c.ZCONTACTJID, '') <> '' "
        "AND COALESCE(c.ZCONTACTJID, '') <> '0@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'"
    ),
    "groups": (
        "SELECT COUNT(*) AS count_value FROM ZWACHATSESSION c "
        "WHERE COALESCE(c.ZARCHIVED, 0) = 0 "
        "AND COALESCE(c.ZCONTACTJID, '') <> '' "
        "AND COALESCE(c.ZCONTACTJID, '') <> '0@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter' "
        "AND COALESCE(c.ZCONTACTJID, '') LIKE '%@g.us'"
    ),
    "archived": (
        "SELECT COUNT(*) AS count_value FROM ZWACHATSESSION c "
        "WHERE COALESCE(c.ZARCHIVED, 0) = 1 "
        "AND COALESCE(c.ZCONTACTJID, '') <> '' "
        "AND COALESCE(c.ZCONTACTJID, '') <> '0@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status' "
        "AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'"
    ),
}

TAB_CHAT_QUERIES = {
    "all": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 0
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
    "groups": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 0
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
          AND COALESCE(c.ZCONTACTJID, '') LIKE '%@g.us'
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
    "archived": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 1
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
}

TAB_CHAT_SEARCH_QUERIES = {
    "all": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 0
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
          AND (COALESCE(c.ZPARTNERNAME, '') LIKE ? OR COALESCE(c.ZCONTACTJID, '') LIKE ?
               OR COALESCE(c.ZLASTMESSAGETEXT, '') LIKE ?)
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
    "groups": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 0
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
          AND COALESCE(c.ZCONTACTJID, '') LIKE '%@g.us'
          AND (COALESCE(c.ZPARTNERNAME, '') LIKE ? OR COALESCE(c.ZCONTACTJID, '') LIKE ?
               OR COALESCE(c.ZLASTMESSAGETEXT, '') LIKE ?)
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
    "archived": """
        SELECT
            c.Z_PK AS chat_id,
            COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
            c.ZCONTACTJID AS contact_jid,
            c.ZUNREADCOUNT AS unread_count,
            c.ZLASTMESSAGEDATE AS last_message_date,
            c.ZLASTMESSAGETEXT AS last_message_text,
            c.ZARCHIVED AS is_archived,
            COALESCE(
                NULLIF(
                    (
                        SELECT p.ZPATH
                        FROM ZWAPROFILEPICTUREITEM p
                        WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                        ORDER BY p.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                ),
                NULLIF(
                    (
                        SELECT gi.ZPICTUREPATH
                        FROM ZWAGROUPINFO gi
                        WHERE gi.ZCHATSESSION = c.Z_PK
                          AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                        ORDER BY gi.Z_PK DESC
                        LIMIT 1
                    ),
                    ''
                )
            ) AS avatar_path
        FROM ZWACHATSESSION c
        WHERE COALESCE(c.ZARCHIVED, 0) = 1
          AND COALESCE(c.ZCONTACTJID, '') <> ''
          AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
          AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
          AND (COALESCE(c.ZPARTNERNAME, '') LIKE ? OR COALESCE(c.ZCONTACTJID, '') LIKE ?
               OR COALESCE(c.ZLASTMESSAGETEXT, '') LIKE ?)
        ORDER BY
            CASE
                WHEN COALESCE(c.ZCONTACTJID, '') = '0@status' THEN 1
                WHEN COALESCE(c.ZLASTMESSAGEDATE, 0) > 2000000000 THEN 1
                ELSE 0
            END ASC,
            c.ZLASTMESSAGEDATE DESC,
            c.Z_PK DESC
        LIMIT ? OFFSET ?
    """,
}

CHAT_BY_ID_QUERY = """
    SELECT
        c.Z_PK AS chat_id,
        COALESCE(NULLIF(c.ZPARTNERNAME, ''), NULLIF(c.ZCONTACTJID, ''), 'Unknown chat') AS chat_name,
        c.ZCONTACTJID AS contact_jid,
        c.ZUNREADCOUNT AS unread_count,
        c.ZLASTMESSAGEDATE AS last_message_date,
        c.ZLASTMESSAGETEXT AS last_message_text,
        c.ZARCHIVED AS is_archived,
        COALESCE(
            NULLIF(
                (
                    SELECT p.ZPATH
                    FROM ZWAPROFILEPICTUREITEM p
                    WHERE COALESCE(p.ZPATH, '') <> ''
                          AND (
                              COALESCE(p.ZPATH, '') LIKE 'Media/Profile/%'
                              OR COALESCE(p.ZPATH, '') LIKE '/Media/Profile/%'
                          )
                          AND (
                              p.ZJID = c.ZCONTACTJID
                              OR p.ZJID LIKE '%' || c.ZCONTACTJID || '%'
                              OR p.ZPATH LIKE 'Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                              OR p.ZPATH LIKE '/Media/Profile/' ||
                              CASE
                                  WHEN instr(c.ZCONTACTJID, '@') > 0
                                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                                  ELSE c.ZCONTACTJID
                              END || '-%'
                          )
                    ORDER BY p.Z_PK DESC
                    LIMIT 1
                ),
                ''
            ),
            NULLIF(
                (
                    SELECT gi.ZPICTUREPATH
                    FROM ZWAGROUPINFO gi
                    WHERE gi.ZCHATSESSION = c.Z_PK
                      AND COALESCE(gi.ZPICTUREPATH, '') <> ''
                    ORDER BY gi.Z_PK DESC
                    LIMIT 1
                ),
                ''
            )
        ) AS avatar_path
    FROM ZWACHATSESSION c
    WHERE c.Z_PK = ?
    LIMIT 1
"""

MESSAGE_QUERY = """
    SELECT
        m.Z_PK AS message_id,
        m.ZCHATSESSION AS chat_id,
        m.ZMESSAGEDATE AS message_date,
        m.ZISFROMME AS is_from_me,
        m.ZMESSAGETYPE AS message_type,
        m.ZTEXT AS text,
        m.ZFROMJID AS from_jid,
        mi.ZMEDIALOCALPATH AS media_path,
        mi.ZVCARDNAME AS vcard_name,
        mi.ZVCARDSTRING AS vcard_value,
        gm.ZCONTACTNAME AS group_contact_name,
        gm.ZFIRSTNAME AS group_first_name,
        gm.ZMEMBERJID AS group_member_jid,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = gm.ZMEMBERJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS group_push_name,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = m.ZFROMJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS from_push_name,
        COALESCE(NULLIF(cs.ZPARTNERNAME, ''), NULLIF(cs.ZCONTACTJID, ''), '') AS direct_chat_name
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
    LEFT JOIN ZWACHATSESSION cs ON cs.Z_PK = m.ZCHATSESSION
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) <> 6
    ORDER BY m.ZMESSAGEDATE DESC, m.Z_PK DESC
    LIMIT ?
"""

MESSAGE_QUERY_WITH_CURSOR = """
    SELECT
        m.Z_PK AS message_id,
        m.ZCHATSESSION AS chat_id,
        m.ZMESSAGEDATE AS message_date,
        m.ZISFROMME AS is_from_me,
        m.ZMESSAGETYPE AS message_type,
        m.ZTEXT AS text,
        m.ZFROMJID AS from_jid,
        mi.ZMEDIALOCALPATH AS media_path,
        mi.ZVCARDNAME AS vcard_name,
        mi.ZVCARDSTRING AS vcard_value,
        gm.ZCONTACTNAME AS group_contact_name,
        gm.ZFIRSTNAME AS group_first_name,
        gm.ZMEMBERJID AS group_member_jid,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = gm.ZMEMBERJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS group_push_name,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = m.ZFROMJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS from_push_name,
        COALESCE(NULLIF(cs.ZPARTNERNAME, ''), NULLIF(cs.ZCONTACTJID, ''), '') AS direct_chat_name
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
    LEFT JOIN ZWACHATSESSION cs ON cs.Z_PK = m.ZCHATSESSION
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) <> 6
      AND (m.ZMESSAGEDATE < ? OR (m.ZMESSAGEDATE = ? AND m.Z_PK < ?))
    ORDER BY m.ZMESSAGEDATE DESC, m.Z_PK DESC
    LIMIT ?
"""

GROUP_INFO_QUERY = """
    SELECT
        ZCREATORJID AS creator_jid,
        ZOWNERJID AS owner_jid,
        ZSOURCEJID AS source_jid,
        ZPICTUREPATH AS picture_path
    FROM ZWAGROUPINFO
    WHERE ZCHATSESSION = ?
    ORDER BY Z_PK DESC
    LIMIT 1
"""

GROUP_MEMBERS_QUERY = """
    SELECT
        ZMEMBERJID AS member_jid,
        ZCONTACTNAME AS contact_name,
        ZFIRSTNAME AS first_name,
        ZISADMIN AS is_admin,
        ZISACTIVE AS is_active,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = gm.ZMEMBERJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS push_name,
        (
            SELECT pi.ZPATH
            FROM ZWAPROFILEPICTUREITEM pi
            WHERE COALESCE(pi.ZPATH, '') <> ''
              AND (
                  COALESCE(pi.ZPATH, '') LIKE 'Media/Profile/%'
                  OR COALESCE(pi.ZPATH, '') LIKE '/Media/Profile/%'
              )
              AND (
                  pi.ZJID = gm.ZMEMBERJID
                  OR pi.ZJID LIKE '%' || gm.ZMEMBERJID || '%'
                  OR pi.ZPATH LIKE 'Media/Profile/' ||
                  CASE
                      WHEN instr(gm.ZMEMBERJID, '@') > 0
                          THEN substr(gm.ZMEMBERJID, 1, instr(gm.ZMEMBERJID, '@') - 1)
                      ELSE gm.ZMEMBERJID
                  END || '-%'
                  OR pi.ZPATH LIKE '/Media/Profile/' ||
                  CASE
                      WHEN instr(gm.ZMEMBERJID, '@') > 0
                          THEN substr(gm.ZMEMBERJID, 1, instr(gm.ZMEMBERJID, '@') - 1)
                      ELSE gm.ZMEMBERJID
                  END || '-%'
              )
            ORDER BY pi.Z_PK DESC
            LIMIT 1
        ) AS avatar_path
    FROM ZWAGROUPMEMBER gm
    WHERE ZCHATSESSION = ?
    ORDER BY COALESCE(ZISADMIN, 0) DESC, COALESCE(ZCONTACTNAME, ZFIRSTNAME, ZMEMBERJID)
    LIMIT 150
"""

CHAT_PUSH_CONFIG_QUERY = """
    SELECT ZMUTEDUNTIL AS muted_until
    FROM ZWACHATPUSHCONFIG
    WHERE ZJID = ?
    ORDER BY Z_PK DESC
    LIMIT 1
"""

CONTACT_PUSH_NAME_QUERY = """
    SELECT ZPUSHNAME AS push_name
    FROM ZWAPROFILEPUSHNAME
    WHERE ZJID = ?
    ORDER BY Z_PK DESC
    LIMIT 1
"""


def _validate_tab(tab: str) -> None:
    """Validate the requested sidebar tab key."""
    if tab not in VALID_TABS:
        raise ValueError(f"Invalid tab: {tab}")


def _jid_to_label(raw_jid: str) -> str:
    """Return a human-friendly local-part for a JID."""
    if not raw_jid:
        return ""
    return raw_jid.split("@", 1)[0]


def _to_chat_summary(row: sqlite3.Row) -> ChatSummary:
    """Convert a SQL chat row into `ChatSummary`."""
    raw_name = row["chat_name"] or row["contact_jid"] or "Unknown chat"
    contact_jid = row["contact_jid"] or ""
    last_message_text = row["last_message_text"] or ""
    return ChatSummary(
        chat_id=int(row["chat_id"]),
        chat_name=str(raw_name),
        contact_jid=str(contact_jid),
        unread_count=int(row["unread_count"] or 0),
        last_message_date=coredata_to_datetime(row["last_message_date"]),
        last_message_text=str(last_message_text),
        is_group=contact_jid.endswith("@g.us"),
        is_archived=bool(row["is_archived"] or 0),
        avatar_path=str(row["avatar_path"]) if row["avatar_path"] else None,
    )


def _tab_count(connection: sqlite3.Connection, tab: str) -> int:
    """Return chat count for a single tab filter."""
    _validate_tab(tab)
    query = TAB_COUNT_QUERIES[tab]
    row = connection.execute(query).fetchone()
    if row is None:
        return 0
    return int(row["count_value"] or 0)


def get_tab_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Return chat counts for all sidebar tabs."""
    return {tab: _tab_count(connection, tab) for tab in ("all", "groups", "archived")}


def list_chats(
    connection: sqlite3.Connection,
    tab: str,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ChatSummary], dict[str, int]]:
    """List chats for a tab with optional search, paging, and fresh counts."""
    _validate_tab(tab)
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if query:
        like_value = f"%{query}%"
        sql = TAB_CHAT_SEARCH_QUERIES[tab]
        rows = connection.execute(sql, [like_value, like_value, like_value, safe_limit, safe_offset]).fetchall()
    else:
        sql = TAB_CHAT_QUERIES[tab]
        rows = connection.execute(sql, [safe_limit, safe_offset]).fetchall()
    chats = [_to_chat_summary(row) for row in rows]
    return chats, get_tab_counts(connection)


def get_chat_by_id(connection: sqlite3.Connection, chat_id: int) -> ChatSummary | None:
    """Fetch one chat summary by primary key."""
    row = connection.execute(CHAT_BY_ID_QUERY, [chat_id]).fetchone()
    if row is None:
        return None
    return _to_chat_summary(row)


def _resolve_sender_name(row: sqlite3.Row) -> str:
    """Resolve sender display name from group/direct message row fields."""
    if bool(row["is_from_me"] or 0):
        return "You"

    group_member_jid = str(row["group_member_jid"] or "").strip()
    has_group_sender = bool(
        group_member_jid or row["group_contact_name"] or row["group_first_name"] or row["group_push_name"]
    )
    if has_group_sender:
        for key in ("group_contact_name", "group_first_name", "group_push_name"):
            value = row[key]
            if value:
                return str(value)
        if group_member_jid:
            return _jid_to_label(group_member_jid)

    direct_chat_name = row["direct_chat_name"]
    if direct_chat_name:
        return str(direct_chat_name)

    from_push_name = row["from_push_name"]
    if from_push_name:
        return str(from_push_name)

    if row["from_jid"]:
        return _jid_to_label(str(row["from_jid"]))
    return "Unknown"


def get_messages(
    connection: sqlite3.Connection,
    chat_id: int,
    before: str | None = None,
    limit: int = 100,
) -> tuple[list[MessageItem], str | None]:
    """Fetch paginated messages for a chat ordered newest-first."""
    safe_limit = max(1, min(limit, 200))
    decoded_cursor = decode_cursor(before)
    if before and decoded_cursor is None:
        raise ValueError("Invalid pagination cursor")

    params: list[object]
    sql: str
    if decoded_cursor is not None:
        message_date, message_id = decoded_cursor
        sql = MESSAGE_QUERY_WITH_CURSOR
        params = [chat_id, message_date, message_date, message_id, safe_limit + 1]
    else:
        sql = MESSAGE_QUERY
        params = [chat_id, safe_limit + 1]

    rows = connection.execute(sql, params).fetchall()

    has_more = len(rows) > safe_limit
    visible_rows = rows[:safe_limit]
    messages = [
        MessageItem(
            message_id=int(row["message_id"]),
            chat_id=int(row["chat_id"]),
            message_date=coredata_to_datetime(row["message_date"]),
            is_from_me=bool(row["is_from_me"] or 0),
            message_type=int(row["message_type"] or 0),
            text=str(row["text"] or ""),
            sender_name=_resolve_sender_name(row),
            sender_jid=(
                str(row["group_member_jid"] or "").strip()
                or str(row["from_jid"] or "").strip()
                or None
            ),
            media_path=str(row["media_path"]) if row["media_path"] else None,
            vcard_name=str(row["vcard_name"]) if row["vcard_name"] else None,
            vcard_value=str(row["vcard_value"]) if row["vcard_value"] else None,
        )
        for row in visible_rows
    ]

    next_before: str | None = None
    if has_more and visible_rows:
        last_row = visible_rows[-1]
        next_before = encode_cursor(float(last_row["message_date"]), int(last_row["message_id"]))

    return messages, next_before


def get_chat_info(connection: sqlite3.Connection, chat_id: int) -> dict[str, Any] | None:
    """Fetch detailed chat info plus group metadata/member rows when applicable."""
    chat = get_chat_by_id(connection, chat_id)
    if chat is None:
        return None

    display_name = chat.chat_name
    if display_name == chat.contact_jid and chat.contact_jid:
        push_name_row = connection.execute(CONTACT_PUSH_NAME_QUERY, [chat.contact_jid]).fetchone()
        if push_name_row and push_name_row["push_name"]:
            display_name = str(push_name_row["push_name"])

    muted_row = None
    if chat.contact_jid:
        muted_row = connection.execute(CHAT_PUSH_CONFIG_QUERY, [chat.contact_jid]).fetchone()

    muted_until = coredata_to_datetime(muted_row["muted_until"]) if muted_row and muted_row["muted_until"] else None

    info: dict[str, Any] = {
        "chat_id": chat.chat_id,
        "chat_name": display_name,
        "contact_jid": chat.contact_jid,
        "unread_count": chat.unread_count,
        "is_group": chat.is_group,
        "is_archived": chat.is_archived,
        "last_message_date": chat.last_message_date.isoformat() if chat.last_message_date else None,
        "avatar_path": chat.avatar_path,
        "muted_until": muted_until.isoformat() if muted_until else None,
        "group": None,
    }

    if not chat.is_group:
        return info

    group_row = connection.execute(GROUP_INFO_QUERY, [chat_id]).fetchone()
    members_rows = connection.execute(GROUP_MEMBERS_QUERY, [chat_id]).fetchall()
    members = []
    for member in members_rows:
        member_name = (
            member["contact_name"]
            or member["first_name"]
            or member["push_name"]
            or _jid_to_label(str(member["member_jid"] or ""))
            or "Unknown"
        )
        members.append(
            {
                "name": str(member_name),
                "jid": str(member["member_jid"] or ""),
                "is_admin": bool(member["is_admin"] or 0),
                "is_active": bool(member["is_active"] or 0),
                "avatar_path": str(member["avatar_path"]) if member["avatar_path"] else None,
            }
        )

    group_picture_path = str(group_row["picture_path"]) if group_row and group_row["picture_path"] else None
    if info["avatar_path"] is None and group_picture_path:
        info["avatar_path"] = group_picture_path

    info["group"] = {
        "creator_jid": str(group_row["creator_jid"] or "") if group_row else "",
        "owner_jid": str(group_row["owner_jid"] or "") if group_row else "",
        "source_jid": str(group_row["source_jid"] or "") if group_row else "",
        "member_count": len(members),
        "members": members,
    }
    return info
