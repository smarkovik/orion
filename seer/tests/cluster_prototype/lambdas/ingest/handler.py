"""Parse one raw scrape object into Postgres, then rebuild the edition's scrape state."""

import difflib
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import unquote, urlsplit

import psycopg
import trafilatura
import yaml
from seer_common import db, store
from seer_common.text import absolute_image, canonical_url, html_to_text, parse_utc

MEDIA_SIZES = ("medium_large", "medium", "large")
IMG_SRC = re.compile(r"<img\b[^>]*?\ssrc=[\"']([^\"']+)[\"']", re.I)
OG_IMAGE = re.compile(
    r"<meta\b[^>]*?(?:property|name)=[\"']og:image(?::url)?[\"'][^>]*?content=[\"']([^\"']+)[\"']", re.I
)
SKIP_SEGMENTS = {"fr", "article"}
CHUNK = 50

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("ingest")


@dataclass
class Counts:
    inserted: int = 0
    updated: int = 0
    changed: int = 0
    refreshed: int = 0
    failures: int = 0
    images: int = 0


def url_categories(url: str) -> list[str]:
    for seg in urlsplit(url).path.split("/"):
        seg = unquote(seg).strip().lower()
        if seg and seg not in SKIP_SEGMENTS and not seg.isdigit():
            return [seg]
    return []


def extract_body(html: str) -> str:
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    if text.strip():
        return text.strip()
    meta = trafilatura.extract_metadata(html)
    return html_to_text(meta.description, keep_breaks=False) if meta and meta.description else ""


def extract_image(html: str, page_url: str) -> str | None:
    match = OG_IMAGE.search(html[:100000])
    if match:
        return absolute_image(unescape(match.group(1)), page_url)
    meta = trafilatura.extract_metadata(html)
    return absolute_image(meta.image, page_url) if meta and meta.image else None


def wp_image(post: dict[str, Any]) -> str | None:
    link = post["link"]
    media = ((post.get("_embedded") or {}).get("wp:featuredmedia") or [{}])[0]
    if isinstance(media, dict):
        sizes = (media.get("media_details") or {}).get("sizes") or {}
        for key in MEDIA_SIZES:
            if (img := absolute_image((sizes.get(key) or {}).get("source_url"), link)) is not None:
                return img
        if (img := absolute_image(media.get("source_url"), link)) is not None:
            return img
    if (img := absolute_image(post.get("jetpack_featured_media_url"), link)) is not None:
        return img
    match = IMG_SRC.search(post["content"]["rendered"])
    return absolute_image(match.group(1), link) if match else None


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()


def map_post(rec: dict[str, Any]) -> dict[str, Any]:
    post = rec["payload"]
    names = rec.get("meta", {}).get("categories", {})
    title = html_to_text(post["title"]["rendered"], keep_breaks=False)
    body = html_to_text(post["content"]["rendered"])
    return {
        "url": canonical_url(post["link"]),
        "external_id": str(post["id"]),
        "title": title,
        "body": body,
        "published_at": datetime.fromisoformat(post["date_gmt"]).replace(tzinfo=timezone.utc),
        "content_hash": content_hash(title, body),
        "source_categories": sorted({names[str(c)] for c in post.get("categories", []) if str(c) in names}),
        "image_url": wp_image(post),
        "source_modified_at": parse_utc(post.get("modified_gmt")),
    }


def map_html(rec: dict[str, Any], published: datetime) -> dict[str, Any]:
    meta = rec.get("meta", {})
    title = meta.get("title") or ""
    html = rec.get("html")
    body = extract_body(html) if html else ""
    image = meta.get("image") or (extract_image(html, rec["loc"]) if html else None)
    return {
        "url": rec["url"],
        "external_id": None,
        "title": title,
        "body": body,
        "published_at": published,
        "content_hash": content_hash(title, body),
        "source_categories": url_categories(rec["loc"]),
        "image_url": image,
        "source_modified_at": parse_utc(meta.get("lastmod")),
    }


def is_meaningful(old: tuple[str, str, str] | None, row: dict[str, Any], min_ratio: float) -> bool:
    if old is None or old[2] == row["content_hash"]:
        return False
    if old[0] != row["title"]:
        return True
    if not old[1]:
        return False
    ratio = difflib.SequenceMatcher(None, old[1][:5000], row["body"][:5000]).ratio()
    return ratio < 1 - min_ratio


UPSERT = """
    INSERT INTO articles (source_id, url, external_id, title, body, published_at, content_hash, source_categories,
                          image_url, source_modified_at, checked_at)
    VALUES (%(source_id)s, %(url)s, %(external_id)s, %(title)s, %(body)s, %(published_at)s, %(content_hash)s,
            %(source_categories)s, %(image_url)s, %(source_modified_at)s, %(checked_at)s)
    ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, body = EXCLUDED.body,
        published_at = EXCLUDED.published_at, content_hash = EXCLUDED.content_hash,
        source_categories = EXCLUDED.source_categories,
        image_url = COALESCE(EXCLUDED.image_url, articles.image_url),
        source_modified_at = COALESCE(EXCLUDED.source_modified_at, articles.source_modified_at),
        checked_at = GREATEST(articles.checked_at, EXCLUDED.checked_at),
        updated_at = CASE WHEN articles.content_hash <> EXCLUDED.content_hash
            OR articles.source_categories IS DISTINCT FROM EXCLUDED.source_categories
            THEN now() ELSE articles.updated_at END,
        content_changed_at = CASE WHEN %(meaningful)s THEN now() ELSE articles.content_changed_at END,
        change_count = articles.change_count + %(meaningful)s::int
"""


def upsert_articles(
    conn: psycopg.Connection, source_id: int, rows: list[dict[str, Any]], counts: Counts, min_ratio: float
) -> None:
    stored = {
        r[0]: (r[1], r[2], r[3])
        for r in conn.execute(
            "SELECT url, title, body, content_hash FROM articles WHERE url = ANY(%s)", ([r["url"] for r in rows],)
        ).fetchall()
    }
    with conn.cursor() as cur:
        for row in rows:
            old = stored.get(row["url"])
            meaningful = is_meaningful(old, row, min_ratio)
            cur.execute(UPSERT, {**row, "source_id": source_id, "meaningful": meaningful})
            if old is None:
                counts.inserted += 1
            elif old[2] != row["content_hash"]:
                counts.updated += 1
            counts.changed += meaningful
            counts.images += row["image_url"] is not None
            stored[row["url"]] = (row["title"], row["body"], row["content_hash"])


def process_source(
    conn: psycopg.Connection, source_id: int, domain: str, records: list[dict[str, Any]], counts: Counts, ratio: float
) -> None:
    rows: list[dict[str, Any]] = []
    touched: list[tuple[str, datetime]] = []
    for rec in records:
        fetched_at = parse_utc(rec.get("fetched_at")) or datetime.now(timezone.utc)
        refresh = bool(rec.get("meta", {}).get("refresh"))
        try:
            if rec["kind"] == "wp_post":
                row = map_post(rec)
            elif rec["kind"] == "html":
                published = parse_utc(rec.get("meta", {}).get("published"))
                if published is None:
                    raise ValueError("no published date")
                if rec.get("error"):
                    counts.failures += 1
                    if refresh:
                        touched.append((rec["url"], fetched_at))
                        continue
                row = map_html(rec, published)
                if not rec.get("error") and not row["body"]:
                    counts.failures += 1
                if refresh:
                    if not row["body"]:
                        touched.append((rec["url"], fetched_at))
                        continue
                    counts.refreshed += 1
            else:
                raise ValueError(f"unknown kind {rec['kind']!r}")
        except (KeyError, TypeError, ValueError, IndexError) as e:
            counts.failures += 1
            log.warning("%s: bad record %s: %r", domain, rec.get("url"), e)
            continue
        rows.append({**row, "checked_at": fetched_at})
    if rows:
        upsert_articles(conn, source_id, rows, counts, ratio)
    for url, at in touched:
        conn.execute("UPDATE articles SET checked_at = GREATEST(checked_at, %s) WHERE url = %s", (at, url))
    conn.commit()


def build_state(
    conn: psycopg.Connection,
    edition: str,
    domains: list[str],
    manifest: dict[str, Any],
    prev: dict[str, Any],
    state_hours: int,
) -> dict[str, Any]:
    started_at = manifest.get("started_at")
    prev_sources = prev.get("sources") or {}
    sources: dict[str, Any] = {}
    for domain in domains:
        info = (manifest.get("sources") or {}).get(domain)
        ok = bool(info) and not info.get("errors") and not info.get("skipped") and not manifest.get("truncated")
        sources[domain] = {"known": {}}
        stamp = started_at if ok else (prev_sources.get(domain) or {}).get("last_ok_started_at")
        if stamp:
            sources[domain]["last_ok_started_at"] = stamp
    rows = conn.execute(
        """
        SELECT s.domain, a.url, a.published_at, a.checked_at, a.body <> ''
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE s.domain = ANY(%s) AND a.published_at >= now() - make_interval(hours => %s)
        """,
        (domains, state_hours),
    ).fetchall()
    for domain, url, published, checked, has_body in rows:
        sources[domain]["known"][url] = {
            "p": published.isoformat(),
            "c": checked.isoformat() if checked else None,
            "b": has_body,
        }
    return {
        "v": 1,
        "edition": edition,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_run_id": manifest.get("run_id"),
        "last_run_started_at": started_at,
        "sources": sources,
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    edition, run_id = event["edition"], event["run_id"]
    ratio = float(os.environ.get("CHANGE_MIN_RATIO", "0.05"))
    state_hours = int(os.environ.get("STATE_HOURS", "48"))
    with open(os.environ.get("SOURCES_FILE", "/var/task/sources.yaml"), encoding="utf-8") as f:
        editions = yaml.safe_load(f)["editions"]
    if edition not in editions:
        raise ValueError(f"unknown edition {edition!r}")
    language = editions[edition].get("language", edition)
    srcs = {s["domain"]: s for s in editions[edition]["sources"]}

    manifest = store.get_json(store.RAW_BUCKET, event["manifest_key"]) or {
        "run_id": run_id,
        "edition": edition,
        "started_at": event.get("started_at"),
        "raw_key": event["raw_key"],
    }
    counts = Counts()
    with db.connect() as conn:
        ids: dict[str, int] = {}
        for domain, src in srcs.items():
            row = conn.execute(
                """
                INSERT INTO sources (name, domain, base_url, language) VALUES (%s, %s, %s, %s)
                ON CONFLICT (domain) DO UPDATE SET name = EXCLUDED.name, base_url = EXCLUDED.base_url,
                    language = EXCLUDED.language
                RETURNING id
                """,
                (src["name"], domain, src["base_url"], language),
            ).fetchone()
            assert row is not None
            ids[domain] = row[0]
        conn.commit()
        pending: dict[str, list[dict[str, Any]]] = {}
        per_source: dict[str, Counts] = {}
        seen: dict[str, int] = {}

        def flush(domain: str) -> None:
            batch = pending.pop(domain, [])
            if batch:
                process_source(conn, ids[domain], domain, batch, per_source.setdefault(domain, Counts()), ratio)

        # Stream the batch; a backfill's raw HTML doesn't fit in memory at once.
        for rec in store.iter_jsonl_gz(store.RAW_BUCKET, event["raw_key"]):
            domain = rec.get("source", "")
            seen[domain] = seen.get(domain, 0) + 1
            if domain not in ids:
                continue
            pending.setdefault(domain, []).append(rec)
            if len(pending[domain]) >= CHUNK:
                flush(domain)
        for domain in list(pending):
            flush(domain)
        for domain, n in seen.items():
            if domain not in ids:
                log.warning("%s: not in sources.yaml for edition %s, %d records skipped", domain, edition, n)
                continue
            c = per_source.get(domain, Counts())
            for k, v in vars(c).items():
                setattr(counts, k, getattr(counts, k) + v)
            log.info(
                "%s: records=%d inserted=%d updated=%d changed=%d refreshed=%d",
                domain,
                n,
                c.inserted,
                c.updated,
                c.changed,
                c.refreshed,
            )
        prev = store.get_json(store.RAW_BUCKET, store.state_key(edition), gz=True) or {}
        state = build_state(
            conn,
            edition,
            list(srcs),
            {**manifest, "started_at": event.get("started_at") or manifest.get("started_at")},
            prev,
            state_hours,
        )
    store.put_json(store.RAW_BUCKET, store.state_key(edition), state, gz=True)

    duration = round(time.monotonic() - t0, 1)
    manifest["ingest"] = {
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inserted": counts.inserted,
        "updated": counts.updated,
        "changed": counts.changed,
        "refreshed": counts.refreshed,
        "failures": counts.failures,
        "duration_s": duration,
    }
    store.put_json(store.RAW_BUCKET, event["manifest_key"], manifest)
    log.info(
        "TOTAL: edition=%s inserted=%d updated=%d changed=%d refreshed=%d failures=%d images=%d in %.1fs",
        edition,
        counts.inserted,
        counts.updated,
        counts.changed,
        counts.refreshed,
        counts.failures,
        counts.images,
        duration,
    )
    return {
        "edition": edition,
        "run_id": run_id,
        "inserted": counts.inserted,
        "updated": counts.updated,
        "changed": counts.changed,
        "refreshed": counts.refreshed,
        "failures": counts.failures,
        "state_key": store.state_key(edition),
        "duration_s": duration,
    }
