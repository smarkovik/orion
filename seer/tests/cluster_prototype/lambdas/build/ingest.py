"""Parse raw scrape records into the in-memory window; same semantics as the former SQL upsert."""

import difflib
import hashlib
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

import trafilatura
from model import BODY_KEEP, Article, Window
from seer_common.text import absolute_image, canonical_url, html_to_text, parse_utc

MEDIA_SIZES = ("medium_large", "medium", "large")
IMG_SRC = re.compile(r"<img\b[^>]*?\ssrc=[\"']([^\"']+)[\"']", re.I)
OG_IMAGE = re.compile(
    r"<meta\b[^>]*?(?:property|name)=[\"']og:image(?::url)?[\"'][^>]*?content=[\"']([^\"']+)[\"']", re.I
)
SKIP_SEGMENTS = {"fr", "article"}
CHANGE_CHARS = 5000

log = logging.getLogger("ingest")


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
        "title": title,
        "body": body,
        "published_at": published,
        "content_hash": content_hash(title, body),
        "source_categories": url_categories(rec["loc"]),
        "image_url": image,
        "source_modified_at": parse_utc(meta.get("lastmod")),
    }


def is_meaningful(old: Article | None, row: dict[str, Any], min_ratio: float) -> bool:
    if old is None or old.content_hash == row["content_hash"]:
        return False
    if old.title != row["title"]:
        return True
    if not old.body:
        return False
    ratio = difflib.SequenceMatcher(None, old.body[:CHANGE_CHARS], row["body"][:CHANGE_CHARS]).ratio()
    return ratio < 1 - min_ratio


def _upsert(
    window: Window, row: dict[str, Any], fetched_at: datetime, now: datetime, ratio: float, counts: dict[str, int]
) -> bool:
    """Returns True when the article was inserted or its hash/categories changed."""
    old = window.articles.get(row["url"])
    counts["images"] += row["image_url"] is not None
    if old is None:
        window.articles[row["url"]] = Article(
            url=row["url"],
            source=row["source"],
            title=row["title"],
            body=row["body"][:BODY_KEEP],
            content_hash=row["content_hash"],
            published_at=row["published_at"],
            first_seen_at=now,
            updated_at=now,
            image_url=row["image_url"],
            source_categories=row["source_categories"],
            source_modified_at=row["source_modified_at"],
            checked_at=fetched_at,
        )
        counts["inserted"] += 1
        return True
    meaningful = is_meaningful(old, row, ratio)
    hash_changed = old.content_hash != row["content_hash"]
    cats_changed = old.source_categories != row["source_categories"]
    old.title = row["title"]
    old.body = row["body"][:BODY_KEEP]
    old.published_at = row["published_at"]
    old.content_hash = row["content_hash"]
    old.source_categories = row["source_categories"]
    old.image_url = row["image_url"] or old.image_url
    old.source_modified_at = row["source_modified_at"] or old.source_modified_at
    old.checked_at = max(old.checked_at, fetched_at) if old.checked_at else fetched_at
    if hash_changed or cats_changed:
        old.updated_at = now
    if meaningful:
        old.content_changed_at = now
        old.change_count += 1
        counts["changed"] += 1
    if hash_changed:
        counts["updated"] += 1
    return hash_changed or cats_changed


def _touch(window: Window, url: str, at: datetime) -> None:
    art = window.articles.get(url)
    if art is not None:
        art.checked_at = max(art.checked_at, at) if art.checked_at else at


def apply_batch(
    window: Window,
    records: Iterable[dict[str, Any]],
    ratio: float,
    now: datetime,
    full_bodies: dict[str, str] | None = None,
    domains: set[str] | None = None,
) -> tuple[dict[str, int], set[str]]:
    """Apply raw records (streamed) to the window. Returns (counts, urls inserted or changed).

    `full_bodies` is filled with the untruncated body of every touched URL (for the archive).
    Records whose source is not in `domains` (when given) are skipped.
    """
    counts = {"inserted": 0, "updated": 0, "changed": 0, "refreshed": 0, "failures": 0, "images": 0}
    touched: set[str] = set()
    for rec in records:
        domain = rec.get("source", "")
        if domains is not None and domain not in domains:
            continue
        fetched_at = parse_utc(rec.get("fetched_at")) or now
        refresh = bool(rec.get("meta", {}).get("refresh"))
        try:
            if rec["kind"] == "wp_post":
                row = map_post(rec)
            elif rec["kind"] == "html":
                published = parse_utc(rec.get("meta", {}).get("published"))
                if published is None:
                    raise ValueError("no published date")
                if rec.get("error"):
                    counts["failures"] += 1
                    if refresh:
                        _touch(window, rec["url"], fetched_at)
                        continue
                row = map_html(rec, published)
                if not rec.get("error") and not row["body"]:
                    counts["failures"] += 1
                if refresh:
                    if not row["body"]:
                        _touch(window, rec["url"], fetched_at)
                        continue
                    counts["refreshed"] += 1
            else:
                raise ValueError(f"unknown kind {rec['kind']!r}")
        except (KeyError, TypeError, ValueError, IndexError) as e:
            counts["failures"] += 1
            log.warning("%s: bad record %s: %r", domain, rec.get("url"), e)
            continue
        row["source"] = domain
        if not row["body"] and rec["kind"] == "html" and row["url"] in window.articles:
            _touch(window, row["url"], fetched_at)  # a failed re-fetch must not blank a stored body
            continue
        if _upsert(window, row, fetched_at, now, ratio, counts):
            touched.add(row["url"])
            if full_bodies is not None:
                full_bodies[row["url"]] = row["body"]
    return counts, touched
