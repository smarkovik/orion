"""Smoke test for Postgres + pgvector. Start the database with ./setup.sh first."""

import os
from collections.abc import Iterator

import pytest

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("SEER_PG_DSN", "postgresql://postgres:seer@localhost:5432/seer")


@pytest.fixture
def conn() -> Iterator["psycopg.Connection"]:
    try:
        connection = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as e:
        pytest.skip(f"Postgres not reachable, run setup.sh: {e}")
    yield connection
    connection.close()


def test_vector_extension_installed(conn: "psycopg.Connection") -> None:
    row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    assert row is not None


def test_cosine_nearest_neighbour_with_hnsw(conn: "psycopg.Connection") -> None:
    conn.execute("CREATE TEMP TABLE articles (id int PRIMARY KEY, embedding vector(3))")
    conn.execute("INSERT INTO articles VALUES (1, '[1,0,0]'), (2, '[0.9,0.1,0]'), (3, '[0,1,0]')")
    conn.execute("CREATE INDEX ON articles USING hnsw (embedding vector_cosine_ops)")
    rows = conn.execute("SELECT id FROM articles ORDER BY embedding <=> '[1,0,0]' LIMIT 2").fetchall()
    assert [r[0] for r in rows] == [1, 2]
