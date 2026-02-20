from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

APPLE_EPOCH_OFFSET = 978307200


def coredata_to_datetime(value: float | int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value) + APPLE_EPOCH_OFFSET, tz=UTC)


def encode_cursor(message_date: float, message_id: int) -> str:
    payload = {"d": float(message_date), "i": int(message_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[float, int] | None:
    if not cursor:
        return None
    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
        payload = json.loads(decoded)
        return float(payload["d"]), int(payload["i"])
    except KeyError, TypeError, ValueError, json.JSONDecodeError:
        return None
