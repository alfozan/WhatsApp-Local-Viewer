from __future__ import annotations

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
    return current_app.config["APP_CONFIG"]


def _parse_int(value: str | None, default_value: int) -> int:
    if value is None:
        return default_value
    try:
        return int(value)
    except ValueError:
        return default_value


def _parse_tab(raw_value: str | None, strict: bool) -> str | None:
    tab = (raw_value or "all").strip().lower()
    if tab in VALID_TABS:
        return tab
    return None if strict else "all"


def _resolve_avatar_attachment(
    candidate_paths: list[str | None],
    contact_jid: str | None = None,
) -> dict[str, Any] | None:
    app_config = _get_app_config()
    fallback_path = find_profile_media_for_jid(contact_jid, app_config.backup_dir) if contact_jid else None

    seen: set[str] = set()
    for raw_path in [*candidate_paths, fallback_path]:
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        media_url = url_for("viewer.media_file", encoded_media_path=encode_media_token(raw_path))
        attachment = build_media_attachment(raw_path, media_url, app_config.backup_dir)
        if attachment.available:
            return attachment.to_dict()
    return None


def _serialize_chat(chat: ChatSummary) -> dict[str, Any]:
    payload = cast(dict[str, Any], chat.to_dict())
    payload["avatar"] = _resolve_avatar_attachment([chat.avatar_path], chat.contact_jid)
    return payload


def _serialize_message(message: MessageItem) -> dict[str, Any]:
    app_config = _get_app_config()
    payload: dict[str, Any] = {
        "message_id": message.message_id,
        "chat_id": message.chat_id,
        "message_date": message.message_date.isoformat() if message.message_date else None,
        "is_from_me": message.is_from_me,
        "message_type": message.message_type,
        "text": message.text,
        "sender_name": message.sender_name,
        "media": None,
    }
    if message.media_path:
        media_url = url_for("viewer.media_file", encoded_media_path=encode_media_token(message.media_path))
        payload["media"] = build_media_attachment(message.media_path, media_url, app_config.backup_dir).to_dict()
    return payload


def _serialize_chat_info_payload(info: dict[str, Any]) -> dict[str, Any]:
    payload = dict(info)
    payload["avatar"] = _resolve_avatar_attachment(
        [str(payload["avatar_path"])] if payload.get("avatar_path") else [],
        str(payload["contact_jid"]) if payload.get("contact_jid") else None,
    )
    if payload.get("group") and isinstance(payload["group"], dict):
        members = payload["group"].get("members") or []
        if isinstance(members, list):
            serialized_members: list[dict[str, Any]] = []
            for member in members:
                member_payload = dict(member)
                member_payload["avatar"] = _resolve_avatar_attachment(
                    [str(member_payload["avatar_path"])] if member_payload.get("avatar_path") else [],
                    str(member_payload["jid"]) if member_payload.get("jid") else None,
                )
                serialized_members.append(member_payload)
            payload["group"]["members"] = serialized_members
    return payload


def _load_initial_state(tab: str, selected_chat_id: int | None) -> tuple[dict[str, Any], str]:
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
            initial_data["messages"] = [_serialize_message(message) for message in messages]
            initial_data["next_before"] = next_before
    except FileNotFoundError as error:
        return initial_data, str(error)

    return initial_data, ""


@viewer.get("/")
def index() -> str:
    tab = _parse_tab(request.args.get("tab"), strict=False) or "all"
    selected_chat_id = _parse_int(request.args.get("chat"), 0) or None
    initial_state, error_message = _load_initial_state(tab=tab, selected_chat_id=selected_chat_id)
    return render_template("index.html", initial_state=initial_state, error_message=error_message)


@viewer.get("/chat/<int:chat_id>")
def chat_view(chat_id: int) -> Any:
    tab = _parse_tab(request.args.get("tab"), strict=False) or "all"
    return redirect(url_for("viewer.index", tab=tab, chat=chat_id))


@viewer.get("/api/chats")
def api_chats() -> tuple[Any, int] | Any:
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

    return jsonify(
        {
            "chat_id": chat_id,
            "next_before": next_before,
            "messages": [_serialize_message(message) for message in messages],
        }
    )


@viewer.get("/api/chats/<int:chat_id>/info")
def api_chat_info(chat_id: int) -> tuple[Any, int] | Any:
    app_config = _get_app_config()
    app_config.validate()

    connection = get_db()
    info = get_chat_info(connection, chat_id)
    if info is None:
        return jsonify({"error": "Chat not found."}), 404
    return jsonify(_serialize_chat_info_payload(info))


@viewer.get("/media/<path:encoded_media_path>")
def media_file(encoded_media_path: str) -> Any:
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
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_mapping(config_overrides or {})

    backup_dir_override = app.config.get("WHATSAPP_BACKUP_DIR")
    app.config["APP_CONFIG"] = AppConfig.from_env(str(backup_dir_override) if backup_dir_override else None)
    app.config.setdefault("JSON_AS_ASCII", False)
    app.teardown_appcontext(close_db)
    app.register_blueprint(viewer)
    return app
