from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

from flask import Blueprint, Flask, abort, current_app, jsonify, redirect, render_template, request, send_file, url_for

from .config import AppConfig
from .db import close_db, get_db
from .media import (
    build_media_attachment,
    decode_media_token,
    encode_media_token,
    find_profile_media_for_jid,
    resolve_media_path,
)
from .models import ChatSummary, MessageItem
from .repository import VALID_TABS, get_chat_by_id, get_chat_info, get_messages, list_chats

viewer = Blueprint("viewer", __name__)


def _get_app_config() -> AppConfig:
    """Return application config stored on the Flask app."""
    return current_app.config["APP_CONFIG"]


def _parse_int(value: str | None, default_value: int) -> int:
    """Parse integer query params with a fallback default."""
    if value is None:
        return default_value
    try:
        return int(value)
    except ValueError:
        return default_value


def _parse_tab(raw_value: str | None, strict: bool) -> str | None:
    """Parse and validate requested tab key from query params."""
    tab = (raw_value or "all").strip().lower()
    if tab in VALID_TABS:
        return tab
    return None if strict else "all"


def _resolve_avatar_attachment(
    candidate_paths: list[str | None],
    contact_jid: str | None = None,
) -> dict[str, Any] | None:
    """Resolve first available avatar attachment from candidate paths."""
    app_config = _get_app_config()
    fallback_path = (
        find_profile_media_for_jid(contact_jid, app_config.backup_dir, app_config.contacts_db_path)
        if contact_jid
        else None
    )

    seen: set[str] = set()
    ordered_paths: list[str | None] = [fallback_path, *candidate_paths]
    for raw_path in ordered_paths:
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        media_url = url_for("viewer.media_file", encoded_media_path=encode_media_token(raw_path))
        attachment = build_media_attachment(raw_path, media_url, app_config.backup_dir)
        if attachment.available:
            return attachment.to_dict()
    return None


def _jid_local_part(jid: str) -> str:
    """Return normalized local-part for a JID-like value."""
    normalized = jid.strip().lower()
    if not normalized:
        return ""
    if "@" in normalized:
        return normalized.split("@", 1)[0]
    return normalized


def _member_label_from_jid(jid: str) -> str:
    """Build fallback member label from JID."""
    local = _jid_local_part(jid)
    return local or jid


def _digits_only(raw_value: str) -> str:
    """Strip non-digit characters from a string."""
    return "".join(char for char in raw_value if char.isdigit())


def _number_from_identifier(identifier: str) -> str:
    """Extract a plausible phone number from supported WhatsApp identifiers."""
    normalized = identifier.strip().lower()
    if not normalized:
        return ""
    if "@" not in normalized:
        return ""
    if normalized.endswith("@lid"):
        return ""
    if "@" in normalized and not normalized.endswith(("@s.whatsapp.net", "@c.us")):
        return ""

    local_part = _jid_local_part(normalized)
    digits = _digits_only(local_part)
    if len(digits) < 8:
        return ""
    return _format_phone_number(digits)


def _member_identity_key(normalized_jid: str, lid: str, whatsapp_id: str, number: str) -> str:
    """Create stable dedupe key for group members."""
    number_digits = _digits_only(number)
    if number_digits:
        return f"num:{number_digits}"

    if whatsapp_id:
        return f"wa:{whatsapp_id}"
    if lid:
        return f"lid:{lid}"
    return f"jid:{normalized_jid}"


def _should_replace_member_name(current_name: str, jid: str) -> bool:
    """Return whether an existing member name should be replaced."""
    cleaned = current_name.strip()
    if not cleaned:
        return True

    lowered = cleaned.lower()
    local = _jid_local_part(jid)
    if lowered in {".", "-", "unknown"}:
        return True
    if lowered == jid.strip().lower():
        return True
    if local and lowered == local:
        return True
    if local and local.isdigit() and cleaned.replace(" ", "") == local:
        return True
    return False


CONTACT_MEMBER_LOOKUP_QUERY = """
    SELECT
        COALESCE(NULLIF(ZFULLNAME, ''), NULLIF(ZGIVENNAME, ''), '') AS resolved_name,
        COALESCE(NULLIF(ZLOCALIZEDPHONENUMBER, ''), NULLIF(ZPHONENUMBER, ''), '') AS resolved_phone,
        COALESCE(ZLID, '') AS lid,
        COALESCE(ZWHATSAPPID, '') AS whatsapp_id
    FROM ZWAADDRESSBOOKCONTACT
    WHERE COALESCE(ZLID, '') = ?
       OR COALESCE(ZWHATSAPPID, '') = ?
       OR (
            CASE
                WHEN instr(COALESCE(ZLID, ''), '@') > 0
                    THEN substr(ZLID, 1, instr(ZLID, '@') - 1)
                ELSE COALESCE(ZLID, '')
            END
        ) = ?
       OR (
            CASE
                WHEN instr(COALESCE(ZWHATSAPPID, ''), '@') > 0
                    THEN substr(ZWHATSAPPID, 1, instr(ZWHATSAPPID, '@') - 1)
                ELSE COALESCE(ZWHATSAPPID, '')
            END
        ) = ?
    ORDER BY
        CASE WHEN COALESCE(ZLID, '') = ? OR COALESCE(ZWHATSAPPID, '') = ? THEN 0 ELSE 1 END,
        Z_PK DESC
    LIMIT 1
"""

CONTACT_DETAILS_LOOKUP_QUERY = """
    SELECT
        COALESCE(NULLIF(ZFULLNAME, ''), NULLIF(ZGIVENNAME, ''), '') AS resolved_name,
        COALESCE(NULLIF(ZLOCALIZEDPHONENUMBER, ''), NULLIF(ZPHONENUMBER, ''), '') AS resolved_phone,
        COALESCE(NULLIF(ZWHATSAPPID, ''), NULLIF(ZLID, ''), '') AS resolved_id
    FROM ZWAADDRESSBOOKCONTACT
    WHERE COALESCE(ZLID, '') = ?
       OR COALESCE(ZWHATSAPPID, '') = ?
       OR (
            CASE
                WHEN instr(COALESCE(ZLID, ''), '@') > 0
                    THEN substr(ZLID, 1, instr(ZLID, '@') - 1)
                ELSE COALESCE(ZLID, '')
            END
        ) = ?
       OR (
            CASE
                WHEN instr(COALESCE(ZWHATSAPPID, ''), '@') > 0
                    THEN substr(ZWHATSAPPID, 1, instr(ZWHATSAPPID, '@') - 1)
                ELSE COALESCE(ZWHATSAPPID, '')
            END
        ) = ?
    ORDER BY
        CASE WHEN COALESCE(ZLID, '') = ? OR COALESCE(ZWHATSAPPID, '') = ? THEN 0 ELSE 1 END,
        Z_PK DESC
    LIMIT 1
"""


def _lookup_member_contact(
    connection: sqlite3.Connection,
    member_jid: str,
) -> dict[str, str]:
    """Resolve member identity, contact name, and phone from Contacts DB."""
    normalized_jid = member_jid.strip().lower()
    local_part = _jid_local_part(normalized_jid)
    row = connection.execute(
        CONTACT_MEMBER_LOOKUP_QUERY,
        [normalized_jid, normalized_jid, local_part, local_part, normalized_jid, normalized_jid],
    ).fetchone()
    if row is None:
        return {"identity_key": f"jid:{normalized_jid}", "name": "", "number": ""}

    lid = str(row["lid"] or "").strip().lower()
    whatsapp_id = str(row["whatsapp_id"] or "").strip().lower()
    resolved_number = _format_phone_number(str(row["resolved_phone"] or "").strip())
    if not resolved_number:
        resolved_number = _number_from_identifier(whatsapp_id)
    identity_key = _member_identity_key(normalized_jid, lid, whatsapp_id, resolved_number)
    resolved_name = str(row["resolved_name"] or "").strip()
    return {"identity_key": identity_key, "name": resolved_name, "number": resolved_number}


def _lookup_contacts_for_members(member_jids: list[str]) -> dict[str, dict[str, str]]:
    """Batch-resolve contact metadata for group member JIDs."""
    app_config = _get_app_config()
    if not app_config.contacts_db_path.exists():
        return {}

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{app_config.contacts_db_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
    except sqlite3.DatabaseError:
        return {}
    resolved_lookup: dict[str, dict[str, str]] = {}
    try:
        normalized_jids = [jid.strip().lower() for jid in member_jids if jid and jid.strip()]
        unique_jids = list(dict.fromkeys(normalized_jids))
        for jid in unique_jids:
            resolved_lookup[jid] = _lookup_member_contact(connection, jid)
    finally:
        if connection is not None:
            connection.close()
    return resolved_lookup


def _format_phone_number(raw_value: str) -> str:
    """Normalize a phone-like value for display."""
    cleaned = raw_value.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("+"):
        return cleaned

    digits_only = "".join(char for char in cleaned if char.isdigit())
    if len(digits_only) >= 8:
        return f"+{digits_only}"
    return cleaned


def _lookup_contact_details(
    identifier: str,
    lookup_cache: dict[str, dict[str, str] | None],
) -> dict[str, str]:
    """Resolve contact name/number fields for a JID or identifier."""
    normalized_identifier = identifier.strip().lower()
    if not normalized_identifier:
        return {"name": "", "number": "", "id": ""}
    if normalized_identifier in lookup_cache:
        return lookup_cache[normalized_identifier] or {"name": "", "number": "", "id": ""}

    app_config = _get_app_config()
    if not app_config.contacts_db_path.exists():
        lookup_cache[normalized_identifier] = None
        return {"name": "", "number": "", "id": ""}

    local_part = _jid_local_part(normalized_identifier)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{app_config.contacts_db_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            CONTACT_DETAILS_LOOKUP_QUERY,
            [
                normalized_identifier,
                normalized_identifier,
                local_part,
                local_part,
                normalized_identifier,
                normalized_identifier,
            ],
        ).fetchone()
    except sqlite3.DatabaseError:
        lookup_cache[normalized_identifier] = None
        return {"name": "", "number": "", "id": ""}
    finally:
        if connection is not None:
            connection.close()

    if row is None:
        lookup_cache[normalized_identifier] = None
        return {"name": "", "number": "", "id": ""}

    payload = {
        "name": str(row["resolved_name"] or "").strip(),
        "number": _format_phone_number(str(row["resolved_phone"] or "")),
        "id": str(row["resolved_id"] or "").strip().lower(),
    }
    lookup_cache[normalized_identifier] = payload
    return payload


def _number_from_jid(contact_jid: str) -> str:
    """Extract phone number from a direct contact WhatsApp JID."""
    normalized = contact_jid.strip().lower()
    if not normalized.endswith("@s.whatsapp.net"):
        return ""
    local_part = _jid_local_part(contact_jid)
    if not local_part or not local_part.isdigit():
        return ""
    return _format_phone_number(local_part)


def _extract_vcard_identifier(message: MessageItem) -> str:
    """Extract best identifier candidate from a vCard-capable message."""
    for value in (message.vcard_value, message.text, message.vcard_name):
        candidate = (value or "").strip()
        if not candidate:
            continue
        if "@" in candidate:
            return candidate
        if candidate.isdigit() and len(candidate) >= 8:
            return candidate
    return ""


def _unfold_vcard_lines(raw_text: str) -> list[str]:
    """Unfold RFC-style wrapped vCard lines."""
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded_lines: list[str] = []
    for line in normalized.split("\n"):
        if unfolded_lines and line.startswith((" ", "\t")):
            unfolded_lines[-1] += line.strip()
        else:
            unfolded_lines.append(line)
    return unfolded_lines


def _decode_vcard_value(value: str) -> str:
    """Decode escaped vCard field values."""
    return value.strip().replace("\\n", "\n").replace("\\;", ";").replace("\\,", ",")


def _apply_vcard_field(parsed: dict[str, Any], field: str, decoded_value: str) -> None:
    """Apply one parsed vCard field into normalized payload dict."""
    if field == "FN" and not parsed["name"]:
        parsed["name"] = decoded_value
        return
    if field == "N" and not parsed["name"]:
        parts = [part for part in decoded_value.split(";") if part]
        parsed["name"] = " ".join(parts).strip()
        return
    if field == "TEL":
        formatted = _format_phone_number(decoded_value)
        if formatted and formatted not in parsed["numbers"]:
            parsed["numbers"].append(formatted)
        return
    if field == "EMAIL" and decoded_value not in parsed["emails"]:
        parsed["emails"].append(decoded_value)
        return
    if field == "ORG" and not parsed["organization"]:
        parsed["organization"] = decoded_value
        return
    if field == "TITLE" and not parsed["title"]:
        parsed["title"] = decoded_value


def _parse_vcard_text(raw_text: str) -> dict[str, Any]:
    """Parse raw vCard text into structured contact data."""
    parsed: dict[str, Any] = {
        "name": "",
        "numbers": [],
        "emails": [],
        "organization": "",
        "title": "",
    }
    for line in _unfold_vcard_lines(raw_text):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        field = key.split(";", 1)[0].strip().upper()
        decoded_value = _decode_vcard_value(value)
        if not decoded_value:
            continue
        _apply_vcard_field(parsed, field, decoded_value)
    return parsed


def _serialize_vcard(message: MessageItem, lookup_cache: dict[str, dict[str, str] | None]) -> dict[str, Any] | None:
    """Serialize message vCard data for frontend rendering."""
    raw_vcard = (message.vcard_value or "").strip()
    raw_text = (message.text or "").strip()
    vcard_text = ""
    for candidate in (raw_vcard, raw_text):
        if "BEGIN:VCARD" in candidate.upper():
            vcard_text = candidate
            break

    if vcard_text:
        parsed = _parse_vcard_text(vcard_text)
        identifier = _extract_vcard_identifier(message)
        lookup = (
            _lookup_contact_details(identifier, lookup_cache) if identifier else {"name": "", "number": "", "id": ""}
        )
        name = parsed["name"] or lookup["name"] or _jid_local_part(identifier)
        numbers = list(parsed["numbers"])
        if lookup["number"] and lookup["number"] not in numbers:
            numbers.append(lookup["number"])
        return {
            "name": name or "Contact",
            "numbers": numbers,
            "emails": parsed["emails"],
            "organization": parsed["organization"],
            "title": parsed["title"],
        }

    if message.message_type != 14:
        return None

    identifier = _extract_vcard_identifier(message)
    if not identifier:
        return {
            "name": "Contact",
            "numbers": [],
            "emails": [],
            "organization": "",
            "title": "",
        }
    lookup = _lookup_contact_details(identifier, lookup_cache)
    number = lookup["number"] or _number_from_jid(identifier)
    return {
        "name": lookup["name"] or _jid_local_part(identifier) or "Contact",
        "numbers": [number] if number else [],
        "emails": [],
        "organization": "",
        "title": "",
    }


def _normalize_group_members(raw_members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate and enrich group members with contact-based names/phones."""
    if not raw_members:
        return []

    members = [dict(member) for member in raw_members if isinstance(member, dict)]
    has_active_flags = any(bool(member.get("is_active")) for member in members)
    if has_active_flags:
        members = [member for member in members if bool(member.get("is_active"))]

    jids = [str(member.get("jid") or "").strip() for member in members if str(member.get("jid") or "").strip()]
    contact_lookup = _lookup_contacts_for_members(jids)

    deduped_members: list[dict[str, Any]] = []
    seen_identity_keys: set[str] = set()
    for member in members:
        member_jid = str(member.get("jid") or "").strip()
        normalized_jid = member_jid.lower()
        lookup = contact_lookup.get(normalized_jid, {})
        identity_key = str(lookup.get("identity_key") or f"jid:{normalized_jid}")
        if identity_key in seen_identity_keys:
            continue
        seen_identity_keys.add(identity_key)

        current_name = str(member.get("name") or "").strip()
        contact_name = str(lookup.get("name") or "").strip()
        if contact_name and (
            _should_replace_member_name(current_name, member_jid) or len(contact_name) > len(current_name)
        ):
            member["name"] = contact_name
        elif not current_name:
            member["name"] = _member_label_from_jid(member_jid) or "Unknown"
        member["phone"] = str(lookup.get("number") or "").strip() or _number_from_identifier(member_jid)

        deduped_members.append(member)

    return deduped_members


def _serialize_chat(chat: ChatSummary) -> dict[str, Any]:
    """Serialize chat summary with resolved avatar payload."""
    payload = cast(dict[str, Any], chat.to_dict())
    payload["avatar"] = _resolve_avatar_attachment([chat.avatar_path], chat.contact_jid)
    return payload


def _serialize_message(
    message: MessageItem,
    contact_lookup_cache: dict[str, dict[str, str] | None],
) -> dict[str, Any]:
    """Serialize one message with media, sender, and vCard enrichment."""
    sender_name = message.sender_name
    sender_key = message.sender_jid or message.sender_name or "unknown"
    if not message.is_from_me and message.sender_jid:
        sender_details = _lookup_contact_details(message.sender_jid, contact_lookup_cache)
        resolved_sender_name = str(sender_details.get("name") or "").strip()
        if resolved_sender_name:
            sender_name = resolved_sender_name

    app_config = _get_app_config()
    payload: dict[str, Any] = {
        "message_id": message.message_id,
        "chat_id": message.chat_id,
        "message_date": message.message_date.isoformat() if message.message_date else None,
        "is_from_me": message.is_from_me,
        "message_type": message.message_type,
        "text": message.text,
        "sender_name": sender_name,
        "sender_key": sender_key,
        "media": None,
        "vcard": _serialize_vcard(message, contact_lookup_cache),
    }
    if message.media_path:
        media_url = url_for("viewer.media_file", encoded_media_path=encode_media_token(message.media_path))
        payload["media"] = build_media_attachment(message.media_path, media_url, app_config.backup_dir).to_dict()
    return payload


def _serialize_chat_info_payload(info: dict[str, Any]) -> dict[str, Any]:
    """Serialize chat info payload with avatar and member enrichment."""
    payload = dict(info)
    lookup_cache: dict[str, dict[str, str] | None] = {}
    contact_jid = str(payload["contact_jid"]) if payload.get("contact_jid") else ""
    contact_details = _lookup_contact_details(contact_jid, lookup_cache) if contact_jid else {"number": "", "name": ""}
    payload["contact_number"] = contact_details.get("number") or _number_from_jid(contact_jid)
    payload["contact_identifier"] = _jid_local_part(contact_jid)
    payload["avatar"] = _resolve_avatar_attachment(
        [str(payload["avatar_path"])] if payload.get("avatar_path") else [],
        contact_jid or None,
    )
    if payload.get("group") and isinstance(payload["group"], dict):
        members = payload["group"].get("members") or []
        if isinstance(members, list):
            members = _normalize_group_members(members)
            serialized_members: list[dict[str, Any]] = []
            for member in members:
                member_payload = dict(member)
                member_payload["avatar"] = _resolve_avatar_attachment(
                    [str(member_payload["avatar_path"])] if member_payload.get("avatar_path") else [],
                    str(member_payload["jid"]) if member_payload.get("jid") else None,
                )
                serialized_members.append(member_payload)
            payload["group"]["members"] = serialized_members
            payload["group"]["member_count"] = len(serialized_members)
    return payload


def _load_initial_state(tab: str, selected_chat_id: int | None) -> tuple[dict[str, Any], str]:
    """Load initial page state used to bootstrap the frontend app."""
    app_config = _get_app_config()
    initial_data: dict[str, Any] = {
        "tab": tab,
        "selected_chat_id": selected_chat_id,
        "counts": {"all": 0, "groups": 0, "archived": 0},
        "chats": [],
        "messages": [],
        "next_before": None,
    }

    try:
        app_config.validate()
        connection = get_db()
        chats, counts = list_chats(connection, tab=tab, query=None, limit=100, offset=0)
        initial_data["counts"] = counts
        initial_data["chats"] = [_serialize_chat(chat) for chat in chats]

        resolved_chat_id = selected_chat_id if selected_chat_id is not None else (chats[0].chat_id if chats else None)
        if resolved_chat_id is not None and get_chat_by_id(connection, resolved_chat_id) is None:
            resolved_chat_id = chats[0].chat_id if chats else None

        initial_data["selected_chat_id"] = resolved_chat_id
        if resolved_chat_id is not None:
            messages, next_before = get_messages(connection, chat_id=resolved_chat_id, limit=100)
            contact_lookup_cache: dict[str, dict[str, str] | None] = {}
            initial_data["messages"] = [
                _serialize_message(message, contact_lookup_cache=contact_lookup_cache) for message in messages
            ]
            initial_data["next_before"] = next_before
    except FileNotFoundError as error:
        return initial_data, str(error)

    return initial_data, ""


@viewer.get("/")
def index() -> str:
    """Render main viewer page with bootstrapped initial state."""
    tab = _parse_tab(request.args.get("tab"), strict=False) or "all"
    selected_chat_id = _parse_int(request.args.get("chat"), 0) or None
    initial_state, error_message = _load_initial_state(tab=tab, selected_chat_id=selected_chat_id)
    return render_template("index.html", initial_state=initial_state, error_message=error_message)


@viewer.get("/chat/<int:chat_id>")
def chat_view(chat_id: int) -> Any:
    """Redirect deep-link chat route into query-param based main view."""
    tab = _parse_tab(request.args.get("tab"), strict=False) or "all"
    return redirect(url_for("viewer.index", tab=tab, chat=chat_id))


@viewer.get("/api/chats")
def api_chats() -> tuple[Any, int] | Any:
    """Return tab-scoped chat list and counts for sidebar rendering."""
    tab = _parse_tab(request.args.get("tab"), strict=True)
    if tab is None:
        return jsonify({"error": "Invalid tab. Allowed values: all, groups, archived."}), 400

    app_config = _get_app_config()
    app_config.validate()
    connection = get_db()
    query_value = (request.args.get("q") or "").strip() or None
    limit = _parse_int(request.args.get("limit"), 100)
    offset = _parse_int(request.args.get("offset"), 0)
    chats, counts = list_chats(connection, tab=tab, query=query_value, limit=limit, offset=offset)
    return jsonify(
        {
            "tab": tab,
            "q": query_value or "",
            "counts": counts,
            "chats": [_serialize_chat(chat) for chat in chats],
        }
    )


@viewer.get("/api/chats/<int:chat_id>/messages")
def api_messages(chat_id: int) -> tuple[Any, int] | Any:
    """Return paginated messages for a chat."""
    app_config = _get_app_config()
    app_config.validate()

    connection = get_db()
    chat = get_chat_by_id(connection, chat_id)
    if chat is None:
        return jsonify({"error": "Chat not found."}), 404

    before = request.args.get("before")
    limit = _parse_int(request.args.get("limit"), 100)
    try:
        messages, next_before = get_messages(connection, chat_id=chat_id, before=before, limit=limit)
    except ValueError:
        return jsonify({"error": "Invalid pagination cursor."}), 400

    contact_lookup_cache: dict[str, dict[str, str] | None] = {}
    return jsonify(
        {
            "chat_id": chat_id,
            "next_before": next_before,
            "messages": [
                _serialize_message(
                    message,
                    contact_lookup_cache=contact_lookup_cache,
                )
                for message in messages
            ],
        }
    )


@viewer.get("/api/chats/<int:chat_id>/info")
def api_chat_info(chat_id: int) -> tuple[Any, int] | Any:
    """Return enriched metadata for a single chat."""
    app_config = _get_app_config()
    app_config.validate()

    connection = get_db()
    info = get_chat_info(connection, chat_id)
    if info is None:
        return jsonify({"error": "Chat not found."}), 404
    return jsonify(_serialize_chat_info_payload(info))


@viewer.get("/media/<path:encoded_media_path>")
def media_file(encoded_media_path: str) -> Any:
    """Serve a media file from backup using an encoded path token."""
    raw_path = decode_media_token(encoded_media_path)
    if raw_path is None:
        abort(404)

    app_config = _get_app_config()
    app_config.validate()
    file_path = resolve_media_path(raw_path, app_config.backup_dir)
    if file_path is None:
        abort(404)
    return send_file(file_path, conditional=True)


def create_app(config_overrides: dict[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application."""
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_mapping(config_overrides or {})

    backup_dir_override = app.config.get("BACKUP_DIR")
    app.config["APP_CONFIG"] = AppConfig.from_path(str(backup_dir_override) if backup_dir_override else None)
    app.config.setdefault("JSON_AS_ASCII", False)
    app.teardown_appcontext(close_db)
    app.register_blueprint(viewer)
    return app
