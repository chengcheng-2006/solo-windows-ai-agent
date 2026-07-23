from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    environment: str = "production"
    database_url: str = "postgresql://paios@127.0.0.1:5432/paios"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8810
    owner_id: str = "owner"
    owner_token: str | None = None
    approval_ttl_seconds: int = 900
    project_root: Path = Path(r"D:\OpenClaw-Hermes-Integration")
    artifact_roots: tuple[Path, ...] = field(
        default_factory=lambda: (
            Path(r"D:\OpenClaw-Hermes-Integration\artifacts"),
            Path(r"D:\OpenClaw-Hermes-Integration\workspaces"),
            Path(r"D:\OpenClaw-Hermes-Integration\tests\runtime-sandbox"),
        )
    )
    test_auth_bypass: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("PAIOS_PROJECT_ROOT", r"D:\OpenClaw-Hermes-Integration"))
        roots_value = os.environ.get("PAIOS_ARTIFACT_ROOTS")
        roots = (
            tuple(Path(item) for item in roots_value.split(os.pathsep) if item)
            if roots_value
            else (root / "artifacts", root / "workspaces", root / "tests" / "runtime-sandbox")
        )
        value = cls(
            environment=os.environ.get("PAIOS_ENV", "production").lower(),
            database_url=os.environ.get("PAIOS_DATABASE_URL", "postgresql://paios@127.0.0.1:5432/paios"),
            bind_host=os.environ.get("PAIOS_BIND_HOST", "127.0.0.1"),
            bind_port=int(os.environ.get("PAIOS_BIND_PORT", "8810")),
            owner_id=os.environ.get("PAIOS_OWNER_ID", "owner"),
            owner_token=os.environ.get("PAIOS_OWNER_TOKEN"),
            approval_ttl_seconds=int(os.environ.get("PAIOS_APPROVAL_TTL_SECONDS", "900")),
            project_root=root,
            artifact_roots=roots,
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.bind_host not in LOOPBACK_HOSTS:
            raise ConfigurationError("PAIOS API must bind to a loopback host")
        if not (1 <= self.bind_port <= 65535):
            raise ConfigurationError("PAIOS_BIND_PORT is invalid")
        if self.environment not in {"production", "development", "test"}:
            raise ConfigurationError("PAIOS_ENV is invalid")
        parsed = urlsplit(self.database_url)
        if self.environment == "test":
            if parsed.scheme not in {"sqlite", "postgresql", "postgres"}:
                raise ConfigurationError("test database scheme is invalid")
        else:
            if parsed.scheme not in {"postgresql", "postgres"}:
                raise ConfigurationError("production PAIOS requires PostgreSQL")
            if parsed.hostname not in LOOPBACK_HOSTS:
                raise ConfigurationError("PostgreSQL must use a loopback host")
            if not self.owner_token:
                raise ConfigurationError("PAIOS_OWNER_TOKEN must be injected at startup")
        if self.approval_ttl_seconds < 30 or self.approval_ttl_seconds > 3600:
            raise ConfigurationError("approval TTL must be between 30 and 3600 seconds")
        for path in (self.project_root, *self.artifact_roots):
            if _is_e_drive(path):
                raise ConfigurationError("E drive is forbidden")


def _is_e_drive(path: Path) -> bool:
    return path.drive.upper() == "E:" or str(path).upper().startswith("E:\\")

