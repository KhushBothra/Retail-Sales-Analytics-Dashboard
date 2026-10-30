from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        password = os.getenv("MYSQL_PASSWORD")
        if not password:
            raise ValueError("MYSQL_PASSWORD is not set.")
        return cls(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "mancino_analytics"),
            user=os.getenv("MYSQL_USER", "analytics_reader"),
            password=password,
        )
