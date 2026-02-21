from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MediaAttachment:
    """Serializable descriptor for a media file associated with a message."""

    raw_path: str
    url: str
    mime_type: str
    kind: str
    file_name: str
    available: bool

    def to_dict(self) -> dict[str, str | bool]:
        """Convert media attachment data into JSON-ready dict form."""
        return {
            "raw_path": self.raw_path,
            "url": self.url,
            "mime_type": self.mime_type,
            "kind": self.kind,
            "file_name": self.file_name,
            "available": self.available,
        }


@dataclass(frozen=True)
class ChatSummary:
    """Sidebar chat list item loaded from `ZWACHATSESSION`."""

    chat_id: int
    chat_name: str
    contact_jid: str
    unread_count: int
    last_message_date: datetime | None
    last_message_text: str
    is_group: bool
    is_archived: bool
    avatar_path: str | None

    def to_dict(self) -> dict[str, str | int | bool | None]:
        """Convert chat summary into JSON-ready dict form."""
        return {
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "contact_jid": self.contact_jid,
            "unread_count": self.unread_count,
            "last_message_date": self.last_message_date.isoformat() if self.last_message_date else None,
            "last_message_text": self.last_message_text,
            "is_group": self.is_group,
            "is_archived": self.is_archived,
            "avatar_path": self.avatar_path,
        }


@dataclass(frozen=True)
class MessageItem:
    """Message row loaded from `ZWAMESSAGE` and related tables."""

    message_id: int
    chat_id: int
    message_date: datetime | None
    is_from_me: bool
    message_type: int
    message_status: int
    text: str
    sender_name: str
    sender_jid: str | None
    media_path: str | None
    media_hd_path: str | None
    media_file_size: int | None
    vcard_name: str | None
    vcard_value: str | None
    parent_message_id: int | None
    parent_message_type: int | None
    parent_message_status: int | None
    parent_is_from_me: bool | None
    parent_text: str | None
    parent_sender_name: str | None
    parent_sender_jid: str | None
    parent_media_path: str | None
    parent_vcard_name: str | None
    parent_vcard_value: str | None
    media_metadata: bytes | None
