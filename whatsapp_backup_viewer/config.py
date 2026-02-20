from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BACKUP_DIR = Path("/Users/alfozan/Local/WhatsApp")


@dataclass(frozen=True)
class AppConfig:
    backup_dir: Path
    chat_db_path: Path

    @classmethod
    def from_env(cls, backup_dir_override: str | None = None) -> "AppConfig":
        backup_dir_value = backup_dir_override or os.getenv("WHATSAPP_BACKUP_DIR")
        backup_dir = Path(backup_dir_value).expanduser() if backup_dir_value else DEFAULT_BACKUP_DIR
        return cls(backup_dir=backup_dir, chat_db_path=backup_dir / "ChatStorage.sqlite")

    def validate(self) -> None:
        if not self.backup_dir.exists():
            raise FileNotFoundError(f"WhatsApp backup directory not found: {self.backup_dir}")
        if not self.chat_db_path.exists():
            raise FileNotFoundError(f"ChatStorage.sqlite not found: {self.chat_db_path}")
