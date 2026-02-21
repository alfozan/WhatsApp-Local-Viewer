from __future__ import annotations

import argparse

from app import create_app


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for running the local Flask server."""
    parser = argparse.ArgumentParser(description="Run WhatsApp Backup Viewer.")
    parser.add_argument(
        "--whatsapp-backup-dir",
        required=True,
        help="Path to copied WhatsApp backup directory (contains ChatStorage.sqlite).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Flask host.")
    parser.add_argument("--port", type=int, default=5000, help="Flask port.")
    return parser.parse_args()


def main() -> None:
    """Create and run the Flask app from CLI arguments."""
    args = _parse_args()
    app = create_app({"WHATSAPP_BACKUP_DIR": args.whatsapp_backup_dir})
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
