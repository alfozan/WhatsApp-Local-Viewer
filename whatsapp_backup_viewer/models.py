from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MediaAttachment:
    raw_path: str
    url: str
    mime_type: str
    kind: str
    file_name: str
    available: bool

    def to_dict(self) -> dict[str, str | bool]:
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
    message_id: int
    chat_id: int
    message_date: datetime | None
    is_from_me: bool
    message_type: int
    text: str
    sender_name: str
    media_path: str | None
