"""Database connection management."""

import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class DatabaseConfig:
    """Database configuration."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize database config from dict."""
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "aipod")
        self.user = config.get("user", "aipod_user")
        
        # Handle password from environment variable if specified
        password_env = config.get("password_env")
        if password_env:
            self.password = os.environ.get(password_env, "")
        else:
            self.password = config.get("password", "")

    @property
    def connection_string(self) -> str:
        """Get psycopg connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


_connection_pool: Optional[ConnectionPool] = None


def get_connection_pool(config: Dict[str, Any]) -> ConnectionPool:
    """Get or create connection pool."""
    global _connection_pool
    if _connection_pool is None:
        db_config = DatabaseConfig(config)
        _connection_pool = ConnectionPool(
            db_config.connection_string,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
    return _connection_pool


@contextmanager
def get_connection(config: Dict[str, Any]) -> Generator[psycopg.Connection, None, None]:
    """Get a database connection from the pool."""
    pool = get_connection_pool(config)
    with pool.connection() as conn:
        yield conn