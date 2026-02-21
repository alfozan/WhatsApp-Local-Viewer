from __future__ import annotations

import sqlite3

from flask import current_app, g

from config import AppConfig


def get_db() -> sqlite3.Connection:
    """Return a cached read-only SQLite connection for the current request."""
    connection = g.get("db_connection")
    if connection is None:
        app_config: AppConfig = current_app.config["APP_CONFIG"]
        database_uri = f"file:{app_config.chat_db_path}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        g.db_connection = connection
    return connection


def close_db(_exception: BaseException | None = None) -> None:
    """Close and clear the request-scoped SQLite connection."""
    connection = g.pop("db_connection", None)
    if connection is not None:
        connection.close()
