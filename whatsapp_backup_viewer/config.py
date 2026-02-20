from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    backup_dir: Path
    chat_db_path: Path
    contacts_db_path: Path

    @classmethod
    def from_path(cls, backup_dir_override: str | None = None) -> "AppConfig":
        backup_dir_value = (backup_dir_override or "").strip()
        if not backup_dir_value:
            raise FileNotFoundError("WhatsApp backup directory is not configured. Pass --backup-dir /path/to/WhatsApp.")
        backup_dir = Path(backup_dir_value).expanduser()
        return cls(
            backup_dir=backup_dir,
            chat_db_path=backup_dir / "ChatStorage.sqlite",
            contacts_db_path=backup_dir / "ContactsV2.sqlite",
        )

    def validate(self) -> None:
        if not self.backup_dir.exists():
            raise FileNotFoundError(f"WhatsApp backup directory not found: {self.backup_dir}")
        if not self.chat_db_path.exists():
            raise FileNotFoundError(f"ChatStorage.sqlite not found: {self.chat_db_path}")
