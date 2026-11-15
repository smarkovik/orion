import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

TZ = ZoneInfo("Europe/Skopje")
EDITIONS = {"mk": "Македонија", "fr": "France"}


def local_dt(value: datetime | None) -> str:
    return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if value else "?"


def safe_url(value: str) -> str:
    return value if value.lower().startswith(("http://", "https://")) else "#"


NONE = "none"


def facet_filter(column: str, value: str | None, alias: str = "c") -> tuple[str, tuple[Any, ...]]:
    if value is None:
        return "", ()
    if value == NONE:
        return f" AND {alias}.{column} IS NULL", ()
    return f" AND {alias}.{column} = %s", (value,)


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(
        os.environ.get("DATABASE_URL", "postgresql://seer:seer@127.0.0.1:5433/seer"),
        row_factory=dict_row,
        connect_timeout=5,
    ) as conn:
        return conn.execute(sql, params).fetchall()  # type: ignore[return-value]


def edition_name(code: str) -> str:
    return EDITIONS.get(code, code)


VIEWS = ("top", "latest")
STORY_ORDER = {"top": "s.score DESC, s.created_at DESC, s.id DESC", "latest": "s.created_at DESC, s.id DESC"}


def load_stories(
    edition: str, view: str, min_sources: int, region: str | None = None, subject: str | None = None
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    region_sql, region_args = facet_filter("region", region, "s")
    subject_sql, subject_args = facet_filter("subject", subject, "s")
    stories = query(
        f"""
        SELECT s.id, s.size, s.source_count, s.first_published, s.last_published, s.score,
               s.region, s.region_votes, s.subject, s.subject_votes,
               a.title AS label_title, a.url AS label_url, a.image_url,
               s.created_at > now() - interval '3 hours' AS is_new,
               coalesce(s.updated_at > now() - interval '6 hours', false) AS is_updated
        FROM stories s JOIN articles a ON a.id = s.label_article_id
        WHERE s.edition = %s AND s.state = 'open' AND s.source_count >= %s{region_sql}{subject_sql}
        ORDER BY {STORY_ORDER[view]}
        """,
        (edition, min_sources, *region_args, *subject_args),
    )
    members: dict[int, list[dict[str, Any]]] = {s["id"]: [] for s in stories}
    if stories:
        rows = query(
            """
            SELECT sa.story_id, sa.similarity, a.title, a.url, a.published_at, a.source_categories,
                   coalesce(a.content_changed_at > now() - interval '6 hours', false) AS changed,
                   src.name AS source_name
            FROM story_articles sa
            JOIN articles a ON a.id = sa.article_id
            JOIN sources src ON src.id = a.source_id
            WHERE sa.story_id = ANY(%s)
            ORDER BY sa.story_id, sa.similarity DESC, a.id
            """,
            (list(members),),
        )
        for row in rows:
            members[row["story_id"]].append(row)
    return stories, members


def story_facets(edition: str, column: str, min_sources: int) -> list[dict[str, Any]]:
    return query(
        f"SELECT coalesce(s.{column}, %s) AS value, count(*) AS n FROM stories s "
        "WHERE s.edition = %s AND s.state = 'open' AND s.source_count >= %s GROUP BY 1 ORDER BY n DESC, value",
        (NONE, edition, min_sources),
    )


def story_editions() -> list[str]:
    rows = query("SELECT DISTINCT edition FROM stories WHERE state = 'open'")
    return [*EDITIONS, *sorted({r["edition"] for r in rows} - set(EDITIONS))]
