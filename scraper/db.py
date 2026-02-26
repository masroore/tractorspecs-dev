from __future__ import annotations

import os
import pathlib
from typing import Any

import asyncpg

from logger import log


async def init_db(dsn: str) -> asyncpg.Pool:
    """Create connection pool and ensure pg_trgm extension exists."""
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    log.info("db.init", dsn=_redact_dsn(dsn))
    return pool


async def close_db(pool: asyncpg.Pool) -> None:
    """Gracefully close the connection pool."""
    await pool.close()
    log.info("db.closed")


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Execute all .sql files from the migrations/ directory in filename order."""
    migrations_dir = pathlib.Path(__file__).parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    async with pool.acquire() as conn:
        for sql_file in sql_files:
            log.info("db.migration", file=sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            await conn.execute(sql)

    log.info("db.migrations_done", count=len(sql_files))


async def execute_returning_id(
    conn: asyncpg.Connection,
    sql: str,
    *args: Any,
) -> int:
    """Execute an INSERT ... RETURNING id statement and return the integer id."""
    row = await conn.fetchrow(sql, *args)
    if row is None:
        raise RuntimeError(f"Query returned no row: {sql!r}")
    return int(row["id"])


def _redact_dsn(dsn: str) -> str:
    """Return DSN with password replaced by ***."""
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(dsn)
        if parsed.password:
            netloc = parsed.netloc.replace(parsed.password, "***")
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return dsn
