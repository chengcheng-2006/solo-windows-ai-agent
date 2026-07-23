from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .database import connect


class MigrationError(RuntimeError):
    pass


def migration_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations"


def available_migrations() -> list[Path]:
    return sorted(migration_directory().glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migration_version(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{path.stem}:{digest}"


def upgrade(settings: Settings) -> list[str]:
    if settings.environment == "test" and settings.database_url.startswith("sqlite"):
        raise MigrationError("production migrations cannot target the SQLite test adapter")
    db = connect(settings)
    applied: list[str] = []
    try:
        with db.transaction():
            db.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version text PRIMARY KEY, applied_at timestamptz NOT NULL)"
            )
        for path in available_migrations():
            version = migration_version(path)
            with db.transaction():
                exists = db.execute(
                    "SELECT version FROM schema_migrations WHERE version=:version",
                    {"version": version},
                ).fetchone()
                if exists:
                    continue
                # Migration files are trusted project assets, never user input.
                db.connection.execute(path.read_text(encoding="utf-8"))
                db.execute(
                    "INSERT INTO schema_migrations(version,applied_at) VALUES(:version,:applied_at)",
                    {"version": version, "applied_at": datetime.now(timezone.utc).isoformat()},
                )
                applied.append(path.name)
    finally:
        db.close()
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply PAIOS PostgreSQL migrations")
    parser.add_argument("command", choices=["upgrade"])
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        applied = upgrade(settings)
        print(f"PAIOS migrations applied: {len(applied)}")
        return 0
    except Exception as exc:
        # Never print a database URL or exception that might contain one.
        print(f"PAIOS migration failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

