from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import Any

from models import ChatSummary, MessageItem
from utils import coredata_to_datetime, decode_cursor, encode_cursor

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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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
                              OR p.ZJID = 'a_' || c.ZCONTACTJID
                              OR p.ZJID LIKE 'om_' || c.ZCONTACTJID || '_%'
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

DIRECT_CHAT_BY_IDENTIFIERS_QUERY = """
    SELECT
        c.Z_PK AS chat_id
    FROM ZWACHATSESSION c
    WHERE COALESCE(c.ZCONTACTJID, '') <> ''
      AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@g.us'
      AND COALESCE(c.ZCONTACTJID, '') <> '0@status'
      AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@status'
      AND COALESCE(c.ZCONTACTJID, '') NOT LIKE '%@newsletter'
      AND (
          c.ZCONTACTJID IN ({placeholders})
          OR (
              CASE
                  WHEN instr(c.ZCONTACTJID, '@') > 0
                      THEN substr(c.ZCONTACTJID, 1, instr(c.ZCONTACTJID, '@') - 1)
                  ELSE c.ZCONTACTJID
              END
          ) = ?
      )
    ORDER BY COALESCE(c.ZLASTMESSAGEDATE, 0) DESC, c.Z_PK DESC
    LIMIT 1
"""

MESSAGE_QUERY = """
    SELECT
        m.Z_PK AS message_id,
        m.ZCHATSESSION AS chat_id,
        m.ZMESSAGEDATE AS message_date,
        m.ZISFROMME AS is_from_me,
        m.ZMESSAGETYPE AS message_type,
        m.ZMESSAGESTATUS AS message_status,
        m.ZTEXT AS text,
        m.ZFROMJID AS from_jid,
        mi.ZMEDIALOCALPATH AS media_path,
        mi.ZFILESIZE AS media_file_size,
        mi.ZMETADATA AS media_metadata,
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
        COALESCE(NULLIF(cs.ZPARTNERNAME, ''), NULLIF(cs.ZCONTACTJID, ''), '') AS direct_chat_name,
        pm.Z_PK AS parent_message_id,
        pm.ZISFROMME AS parent_is_from_me,
        pm.ZMESSAGETYPE AS parent_message_type,
        pm.ZMESSAGESTATUS AS parent_message_status,
        pm.ZTEXT AS parent_text,
        pm.ZFROMJID AS parent_from_jid,
        pmi.ZMEDIALOCALPATH AS parent_media_path,
        pmi.ZVCARDNAME AS parent_vcard_name,
        pmi.ZVCARDSTRING AS parent_vcard_value,
        pgm.ZCONTACTNAME AS parent_group_contact_name,
        pgm.ZFIRSTNAME AS parent_group_first_name,
        pgm.ZMEMBERJID AS parent_group_member_jid,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = pgm.ZMEMBERJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS parent_group_push_name,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = pm.ZFROMJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS parent_from_push_name
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
    LEFT JOIN ZWAMESSAGE pm ON pm.Z_PK = m.ZPARENTMESSAGE
    LEFT JOIN ZWAMEDIAITEM pmi ON pmi.Z_PK = pm.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER pgm ON pgm.Z_PK = pm.ZGROUPMEMBER
    LEFT JOIN ZWACHATSESSION cs ON cs.Z_PK = m.ZCHATSESSION
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) <> 6
      AND (
          COALESCE(m.ZTEXT, '') <> ''
          OR COALESCE(mi.ZMEDIALOCALPATH, '') <> ''
          OR COALESCE(mi.ZVCARDSTRING, '') <> ''
          OR COALESCE(mi.ZVCARDNAME, '') <> ''
          OR COALESCE(m.ZMESSAGETYPE, 0) IN (14, 46, 59)
      )
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
        m.ZMESSAGESTATUS AS message_status,
        m.ZTEXT AS text,
        m.ZFROMJID AS from_jid,
        mi.ZMEDIALOCALPATH AS media_path,
        mi.ZFILESIZE AS media_file_size,
        mi.ZMETADATA AS media_metadata,
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
        COALESCE(NULLIF(cs.ZPARTNERNAME, ''), NULLIF(cs.ZCONTACTJID, ''), '') AS direct_chat_name,
        pm.Z_PK AS parent_message_id,
        pm.ZISFROMME AS parent_is_from_me,
        pm.ZMESSAGETYPE AS parent_message_type,
        pm.ZMESSAGESTATUS AS parent_message_status,
        pm.ZTEXT AS parent_text,
        pm.ZFROMJID AS parent_from_jid,
        pmi.ZMEDIALOCALPATH AS parent_media_path,
        pmi.ZVCARDNAME AS parent_vcard_name,
        pmi.ZVCARDSTRING AS parent_vcard_value,
        pgm.ZCONTACTNAME AS parent_group_contact_name,
        pgm.ZFIRSTNAME AS parent_group_first_name,
        pgm.ZMEMBERJID AS parent_group_member_jid,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = pgm.ZMEMBERJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS parent_group_push_name,
        (
            SELECT p.ZPUSHNAME
            FROM ZWAPROFILEPUSHNAME p
            WHERE p.ZJID = pm.ZFROMJID
              AND COALESCE(p.ZPUSHNAME, '') <> ''
            ORDER BY p.Z_PK DESC
            LIMIT 1
        ) AS parent_from_push_name
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER gm ON gm.Z_PK = m.ZGROUPMEMBER
    LEFT JOIN ZWAMESSAGE pm ON pm.Z_PK = m.ZPARENTMESSAGE
    LEFT JOIN ZWAMEDIAITEM pmi ON pmi.Z_PK = pm.ZMEDIAITEM
    LEFT JOIN ZWAGROUPMEMBER pgm ON pgm.Z_PK = pm.ZGROUPMEMBER
    LEFT JOIN ZWACHATSESSION cs ON cs.Z_PK = m.ZCHATSESSION
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) <> 6
      AND (
          COALESCE(m.ZTEXT, '') <> ''
          OR COALESCE(mi.ZMEDIALOCALPATH, '') <> ''
          OR COALESCE(mi.ZVCARDSTRING, '') <> ''
          OR COALESCE(mi.ZVCARDNAME, '') <> ''
          OR COALESCE(m.ZMESSAGETYPE, 0) IN (14, 46, 59)
      )
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
                  OR pi.ZJID = 'a_' || gm.ZMEMBERJID
                  OR pi.ZJID LIKE 'om_' || gm.ZMEMBERJID || '_%'
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

LATEST_CHAT_PREVIEW_QUERY = """
    SELECT
        m.ZMESSAGEDATE AS message_date,
        CASE
            WHEN COALESCE(m.ZMESSAGETYPE, 0) = 59 THEN 'This message was deleted.'
            WHEN COALESCE(m.ZMESSAGETYPE, 0) = 14 THEN
                CASE
                    WHEN COALESCE(m.ZISFROMME, 0) = 0 THEN 'Missed voice call'
                    ELSE 'Voice call'
                END
            WHEN COALESCE(m.ZMESSAGETYPE, 0) = 46 THEN 'Poll'
            WHEN COALESCE(m.ZTEXT, '') <> '' THEN COALESCE(m.ZTEXT, '')
            WHEN COALESCE(m.ZMESSAGETYPE, 0) = 4
                 OR UPPER(COALESCE(mi.ZVCARDSTRING, '')) LIKE '%BEGIN:VCARD%'
                 OR UPPER(COALESCE(m.ZTEXT, '')) LIKE '%BEGIN:VCARD%' THEN 'Contact card'
            WHEN COALESCE(mi.ZMEDIALOCALPATH, '') <> '' THEN 'Media'
            ELSE ''
        END AS preview_text
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) NOT IN (6, 10)
      AND (
          COALESCE(m.ZTEXT, '') <> ''
          OR COALESCE(mi.ZMEDIALOCALPATH, '') <> ''
          OR COALESCE(mi.ZVCARDSTRING, '') <> ''
          OR COALESCE(mi.ZVCARDNAME, '') <> ''
          OR COALESCE(m.ZMESSAGETYPE, 0) IN (14, 46, 59)
      )
    ORDER BY m.ZMESSAGEDATE DESC, m.Z_PK DESC
    LIMIT 1
"""

RECENT_MESSAGES_FOR_UNREAD_QUERY = """
    SELECT
        COALESCE(m.ZISFROMME, 0) AS is_from_me,
        COALESCE(m.ZMESSAGESTATUS, 0) AS message_status,
        COALESCE(m.ZMESSAGETYPE, 0) AS message_type,
        COALESCE(m.ZFROMJID, '') AS from_jid,
        COALESCE(m.ZTEXT, '') AS text,
        COALESCE(mi.ZMEDIALOCALPATH, '') AS media_path,
        COALESCE(mi.ZFILESIZE, 0) AS file_size
    FROM ZWAMESSAGE m
    LEFT JOIN ZWAMEDIAITEM mi ON mi.Z_PK = m.ZMEDIAITEM
    WHERE m.ZCHATSESSION = ?
      AND COALESCE(m.ZMESSAGETYPE, 0) NOT IN (6, 10)
    ORDER BY m.ZMESSAGEDATE DESC, m.Z_PK DESC
    LIMIT ?
"""

UNREAD_MESSAGE_STATUSES = {6}
UNREAD_SCAN_LIMIT = 120
SMALL_IMAGE_FILE_SIZE_BYTES = 150_000
LARGE_IMAGE_FILE_SIZE_BYTES = 500_000


def _latest_chat_previews(connection: sqlite3.Connection, chat_ids: list[int]) -> dict[int, tuple[float, str]]:
    """Return latest displayable `(message_date, preview_text)` per chat."""
    if not chat_ids:
        return {}

    previews: dict[int, tuple[float, str]] = {}
    for chat_id in dict.fromkeys(chat_ids):
        row = connection.execute(LATEST_CHAT_PREVIEW_QUERY, [chat_id]).fetchone()
        if row is None or row["message_date"] is None:
            continue
        previews[int(chat_id)] = (float(row["message_date"]), str(row["preview_text"] or ""))
    return previews


def _apply_latest_chat_previews(
    connection: sqlite3.Connection,
    chats: list[ChatSummary],
) -> list[ChatSummary]:
    """Overlay chat summaries with latest displayable preview text/date."""
    previews = _latest_chat_previews(connection, [chat.chat_id for chat in chats])
    if not previews:
        return chats

    updated: list[ChatSummary] = []
    for chat in chats:
        preview = previews.get(chat.chat_id)
        if preview is None:
            updated.append(chat)
            continue
        preview_date_raw, preview_text = preview
        updated.append(
            replace(
                chat,
                last_message_date=coredata_to_datetime(preview_date_raw),
                last_message_text=preview_text,
            )
        )
    return updated


def _collapse_unread_image_duplicates(rows: list[sqlite3.Row]) -> int:
    """Collapse likely duplicated image rows into logical unread image count."""
    if not rows:
        return 0

    if not _is_single_sender_image_batch(rows):
        return len(rows)

    small_images, large_images = _image_size_buckets(rows)
    if small_images == 0 or large_images == 0:
        return len(rows)
    if small_images + large_images != len(rows):
        return len(rows)

    return max(small_images, large_images)


def _is_single_sender_image_batch(rows: list[sqlite3.Row]) -> bool:
    """Return whether unread rows are plain images from one sender."""
    senders = {str(row["from_jid"] or "").strip() for row in rows}
    if len(senders) != 1:
        return False
    for row in rows:
        if int(row["message_type"] or 0) != 1:
            return False
        if not str(row["media_path"] or "").strip():
            return False
        if str(row["text"] or "").strip():
            return False
    return True


def _image_size_buckets(rows: list[sqlite3.Row]) -> tuple[int, int]:
    """Count image rows in small/large file-size buckets."""
    small_images = 0
    large_images = 0
    for row in rows:
        file_size = int(row["file_size"] or 0)
        if 0 < file_size < SMALL_IMAGE_FILE_SIZE_BYTES:
            small_images += 1
            continue
        if file_size >= LARGE_IMAGE_FILE_SIZE_BYTES:
            large_images += 1
    return small_images, large_images


def _derived_unread_count(connection: sqlite3.Connection, chat_id: int) -> int:
    """Derive unread count from the newest contiguous incoming unread message run."""
    rows = connection.execute(RECENT_MESSAGES_FOR_UNREAD_QUERY, [chat_id, UNREAD_SCAN_LIMIT]).fetchall()
    if not rows:
        return 0

    unread_rows: list[sqlite3.Row] = []
    for row in rows:
        if bool(row["is_from_me"] or 0):
            break
        if int(row["message_status"] or 0) not in UNREAD_MESSAGE_STATUSES:
            break
        unread_rows.append(row)

    if not unread_rows:
        return 0
    return _collapse_unread_image_duplicates(unread_rows)


def _apply_derived_unread_counts(
    connection: sqlite3.Connection,
    chats: list[ChatSummary],
) -> list[ChatSummary]:
    """Replace raw chat unread counters with derived unread counters."""
    updated: list[ChatSummary] = []
    for chat in chats:
        unread_count = _derived_unread_count(connection, chat.chat_id)
        updated.append(replace(chat, unread_count=unread_count))
    return updated


def _is_media_variant_candidate(message: MessageItem) -> bool:
    """Return whether a message is a plain image candidate for variant collapsing."""
    return (
        message.message_type == 1
        and not message.text.strip()
        and message.media_path is not None
        and (message.media_file_size or 0) > 0
        and message.parent_message_id is None
    )


def _collapse_image_variant_messages(messages: list[MessageItem]) -> list[MessageItem]:
    """Merge adjacent preview/HD image variants into a single display message."""
    if len(messages) < 2:
        return messages

    collapsed: list[MessageItem] = []
    i = 0
    while i < len(messages):
        current = messages[i]
        if i + 1 >= len(messages):
            collapsed.append(current)
            break

        nxt = messages[i + 1]
        if not (_is_media_variant_candidate(current) and _is_media_variant_candidate(nxt)):
            collapsed.append(current)
            i += 1
            continue

        same_sender = (current.sender_jid or "") == (nxt.sender_jid or "")
        same_direction = current.is_from_me == nxt.is_from_me
        if not (same_sender and same_direction and current.message_date and nxt.message_date):
            collapsed.append(current)
            i += 1
            continue

        seconds_delta = abs((current.message_date - nxt.message_date).total_seconds())
        if seconds_delta > 2:
            collapsed.append(current)
            i += 1
            continue

        current_size = int(current.media_file_size or 0)
        next_size = int(nxt.media_file_size or 0)
        sizes = sorted((current_size, next_size))
        if not (sizes[0] < SMALL_IMAGE_FILE_SIZE_BYTES and sizes[1] >= LARGE_IMAGE_FILE_SIZE_BYTES):
            collapsed.append(current)
            i += 1
            continue

        preview_message = current if current_size <= next_size else nxt
        hd_message = current if current_size > next_size else nxt
        merged = replace(
            current,
            media_path=preview_message.media_path,
            media_hd_path=hd_message.media_path,
            media_file_size=preview_message.media_file_size,
        )
        collapsed.append(merged)
        i += 2
    return collapsed


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
    unread_count = max(0, int(row["unread_count"] or 0))
    return ChatSummary(
        chat_id=int(row["chat_id"]),
        chat_name=str(raw_name),
        contact_jid=str(contact_jid),
        unread_count=unread_count,
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
    chats = _apply_derived_unread_counts(connection, chats)
    chats = _apply_latest_chat_previews(connection, chats)
    return chats, get_tab_counts(connection)


def get_chat_by_id(connection: sqlite3.Connection, chat_id: int) -> ChatSummary | None:
    """Fetch one chat summary by primary key."""
    row = connection.execute(CHAT_BY_ID_QUERY, [chat_id]).fetchone()
    if row is None:
        return None
    chat = _to_chat_summary(row)
    unread_count = _derived_unread_count(connection, chat.chat_id)
    return replace(chat, unread_count=unread_count)


def find_direct_chat_id(
    connection: sqlite3.Connection,
    identifiers: list[str],
    local_part: str,
) -> int | None:
    """Find direct-chat id by possible JID identifiers and local part."""
    normalized_identifiers = [value.strip().lower() for value in identifiers if value and value.strip()]
    if not normalized_identifiers and not local_part:
        return None

    if normalized_identifiers:
        placeholders = ", ".join("?" for _ in normalized_identifiers)
        query = DIRECT_CHAT_BY_IDENTIFIERS_QUERY.format(placeholders=placeholders)
        row = connection.execute(query, [*normalized_identifiers, local_part]).fetchone()
    else:
        query = DIRECT_CHAT_BY_IDENTIFIERS_QUERY.format(placeholders="''")
        row = connection.execute(query, [local_part]).fetchone()

    if row is None:
        return None
    return int(row["chat_id"])


def _resolve_sender_name(row: sqlite3.Row, prefix: str = "") -> str:
    """Resolve sender display name from group/direct message row fields."""
    if bool(row[f"{prefix}is_from_me"] or 0):
        return "You"

    group_member_jid = str(row[f"{prefix}group_member_jid"] or "").strip()
    has_group_sender = bool(
        group_member_jid
        or row[f"{prefix}group_contact_name"]
        or row[f"{prefix}group_first_name"]
        or row[f"{prefix}group_push_name"]
    )
    if has_group_sender:
        for key in ("group_contact_name", "group_first_name", "group_push_name"):
            value = row[f"{prefix}{key}"]
            if value:
                return str(value)
        if group_member_jid:
            return _jid_to_label(group_member_jid)

    direct_chat_name = row["direct_chat_name"]
    if direct_chat_name:
        return str(direct_chat_name)

    from_push_name = row[f"{prefix}from_push_name"]
    if from_push_name:
        return str(from_push_name)

    if row[f"{prefix}from_jid"]:
        return _jid_to_label(str(row[f"{prefix}from_jid"]))
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
            message_status=int(row["message_status"] or 0),
            text=str(row["text"] or ""),
            sender_name=_resolve_sender_name(row),
            sender_jid=(str(row["group_member_jid"] or "").strip() or str(row["from_jid"] or "").strip() or None),
            media_path=str(row["media_path"]) if row["media_path"] else None,
            media_hd_path=None,
            media_file_size=int(row["media_file_size"]) if row["media_file_size"] is not None else None,
            vcard_name=str(row["vcard_name"]) if row["vcard_name"] else None,
            vcard_value=str(row["vcard_value"]) if row["vcard_value"] else None,
            parent_message_id=int(row["parent_message_id"]) if row["parent_message_id"] else None,
            parent_message_type=int(row["parent_message_type"]) if row["parent_message_type"] is not None else None,
            parent_message_status=(
                int(row["parent_message_status"]) if row["parent_message_status"] is not None else None
            ),
            parent_is_from_me=bool(row["parent_is_from_me"] or 0) if row["parent_message_id"] else None,
            parent_text=str(row["parent_text"] or "") if row["parent_message_id"] else None,
            parent_sender_name=_resolve_sender_name(row, prefix="parent_") if row["parent_message_id"] else None,
            parent_sender_jid=(
                (str(row["parent_group_member_jid"] or "").strip() or str(row["parent_from_jid"] or "").strip() or None)
                if row["parent_message_id"]
                else None
            ),
            parent_media_path=str(row["parent_media_path"]) if row["parent_media_path"] else None,
            parent_vcard_name=str(row["parent_vcard_name"]) if row["parent_vcard_name"] else None,
            parent_vcard_value=str(row["parent_vcard_value"]) if row["parent_vcard_value"] else None,
            media_metadata=bytes(row["media_metadata"]) if row["media_metadata"] is not None else None,
        )
        for row in visible_rows
    ]
    messages = _collapse_image_variant_messages(messages)

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
