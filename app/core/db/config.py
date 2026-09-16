import os
from dataclasses import dataclass

@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    echo: bool = False
    pool_pre_ping: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            raise RuntimeError("DATABASE_URL is required")
        # Normalize common postgres URL forms.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return cls(
            url=url,
            echo=os.getenv("SQL_ECHO", "").lower() in {"1", "true", "yes"},
        )
