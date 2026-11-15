"""Postgres connection with retries, since a paused Aurora cluster takes ~15 s to resume."""

import os
import time

import psycopg

ATTEMPTS = int(os.environ.get("DB_CONNECT_ATTEMPTS", "4"))


def connect(autocommit: bool = False) -> psycopg.Connection:
    for attempt in range(ATTEMPTS):
        try:
            return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=30, autocommit=autocommit)
        except psycopg.OperationalError:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")
