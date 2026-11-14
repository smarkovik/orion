"""Scrape recent articles (WordPress API or news sitemap) into Postgres."""

import difflib
import hashlib
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import psycopg
import trafilatura
import yaml

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
MAX_PAGES = 10
MAX_CHILD_SITEMAPS = 5
RETRIES = 2
FIELDS = "id,date_gmt,modified_gmt,link,title,content,categories,jetpack_featured_media_url,_links,_embedded"
MEDIA_SIZES = ("medium_large", "medium", "large")
IMG_SRC = re.compile(r"<img\b[^>]*?\ssrc=[\"']([^\"']+)[\"']", re.I)
OG_IMAGE = re.compile(
    r"<meta\b[^>]*?(?:property|name)=[\"']og:image(?::url)?[\"'][^>]*?content=[\"']([^\"']+)[\"']", re.I
)
CHANGE_MIN_RATIO = float(os.environ.get("CHANGE_MIN_RATIO", "0.05"))
RECHECK_MINUTES = 60
DROP_PARAMS = ("utm_", "at_")
DROP_EXACT = {"fbclid", "gclid"}
BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "figure"}
SKIP_TAGS = {"script", "style"}
SKIP_SEGMENTS = {"fr", "article"}

logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("scraper")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str, keep_breaks: bool = True) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    parser.close()
    text = unescape("".join(parser.parts)).replace("\xa0", " ")
    if not keep_breaks:
        return re.sub(r"\s+", " ", text).strip()
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def canonical_url(link: str) -> str:
    parts = urlsplit(link.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port:
        host = f"{host}:{parts.port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in DROP_EXACT and not k.startswith(DROP_PARAMS)
    ]
    return urlunsplit((parts.scheme.lower(), host, parts.path, urlencode(query), ""))


def absolute_image(url: Any, base: str) -> str | None:
    if not isinstance(url, str) or not url.strip() or url.strip().startswith("data:"):
        return None
    full = urljoin(base, url.strip())
    return full if full.startswith(("http://", "https://")) else None


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


def parse_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def map_post(post: dict[str, Any], category_names: dict[int, str]) -> dict[str, Any]:
    title = html_to_text(post["title"]["rendered"], keep_breaks=False)
    body = html_to_text(post["content"]["rendered"])
    published = datetime.fromisoformat(post["date_gmt"]).replace(tzinfo=timezone.utc)
    return {
        "url": canonical_url(post["link"]),
        "external_id": str(post["id"]),
        "title": title,
        "body": body,
        "published_at": published,
        "content_hash": hashlib.sha256(f"{title}\n{body}".encode()).hexdigest(),
        "source_categories": sorted({category_names[c] for c in post.get("categories", []) if c in category_names}),
        "image_url": wp_image(post),
        "source_modified_at": parse_utc(post.get("modified_gmt")),
    }


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(xml: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (child sitemap URLs, entries with loc/title/published) from a sitemap or sitemap index."""
    root = ET.fromstring(xml)
    children: list[str] = []
    entries: list[dict[str, Any]] = []
    for node in root:
        kind = local_name(node.tag)
        if kind not in ("sitemap", "url"):
            continue
        fields: dict[str, str] = {}
        image = ""
        for child in node:
            name = local_name(child.tag)
            if name == "image":
                image = image or next((e.text or "" for e in child if local_name(e.tag) == "loc"), "").strip()
            elif name in ("loc", "lastmod"):
                fields.setdefault(name, (child.text or "").strip())
            else:
                for el in child.iter():
                    fields.setdefault(local_name(el.tag), (el.text or "").strip())
        if kind == "sitemap":
            if fields.get("loc"):
                children.append(fields["loc"])
            continue
        raw_date = fields.get("publication_date")
        if not fields.get("loc") or not raw_date:
            continue
        published = parse_utc(raw_date)
        if published is None:
            continue
        title = html_to_text(fields.get("title", ""), keep_breaks=False)
        entries.append(
            {
                "loc": fields["loc"],
                "title": title,
                "published": published,
                "image": absolute_image(image, fields["loc"]),
                "lastmod": parse_utc(fields.get("lastmod")),
            }
        )
    return children, entries


def url_categories(url: str) -> list[str]:
    for seg in urlsplit(url).path.split("/"):
        seg = unquote(seg).strip().lower()
        if seg and seg not in SKIP_SEGMENTS and not seg.isdigit():
            return [seg]
    return []


def is_challenge(html: str) -> bool:
    head = html[:3000]
    return "Just a moment" in head or "dd={" in head


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


@dataclass
class Result:
    domain: str
    method: str = ""
    pages: int = 0
    posts: int = 0
    fetched: int = 0
    failures: int = 0
    inserted: int = 0
    updated: int = 0
    images: int = 0
    changed: int = 0
    refreshed: int = 0
    errors: int = 0
    skipped: bool = False


class Fetcher:
    """Sequential, rate-limited, retrying client for one host."""

    def __init__(self, delay: float) -> None:
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        self.delay = delay
        self._last = 0.0

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for attempt in range(RETRIES + 1):
            wait = self._last + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.client.get(url, params=params)
                self._last = time.monotonic()
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
                err: Exception = httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
            except httpx.TimeoutException as e:
                self._last = time.monotonic()
                err = e
            if attempt == RETRIES:
                raise err
            time.sleep(2 ** (attempt + 1))
        raise RuntimeError("unreachable")


def robots_allowed(fetcher: Fetcher, base_url: str, api_url: str) -> bool:
    try:
        resp = fetcher.client.get(f"{base_url}/robots.txt")
    except httpx.HTTPError:
        return True
    rp = RobotFileParser()
    if resp.status_code in (401, 403):
        return False
    if resp.status_code >= 400:
        return True
    rp.parse(resp.text.splitlines())
    return rp.can_fetch(UA, api_url)


def fetch_categories(fetcher: Fetcher, base: str) -> dict[int, str]:
    names: dict[int, str] = {}
    page, total = 1, 1
    while page <= min(total, MAX_PAGES):
        resp = fetcher.get(f"{base}/wp-json/wp/v2/categories", {"per_page": 100, "page": page, "_fields": "id,name"})
        total = int(resp.headers.get("X-WP-TotalPages", 1))
        names.update({c["id"]: html_to_text(c["name"], keep_breaks=False) for c in resp.json()})
        page += 1
    return names


def is_meaningful(old: tuple[str, str, str] | None, row: dict[str, Any]) -> bool:
    if old is None or old[2] == row["content_hash"]:
        return False
    if old[0] != row["title"]:
        return True
    if not old[1]:
        return False
    ratio = difflib.SequenceMatcher(None, old[1][:5000], row["body"][:5000]).ratio()
    return ratio < 1 - CHANGE_MIN_RATIO


def upsert_articles(conn: psycopg.Connection, source_id: int, rows: list[dict[str, Any]], res: Result) -> None:
    sql = """
        INSERT INTO articles (source_id, url, external_id, title, body, published_at, content_hash, source_categories,
                              image_url, source_modified_at, checked_at)
        VALUES (%(source_id)s, %(url)s, %(external_id)s, %(title)s, %(body)s, %(published_at)s, %(content_hash)s,
                %(source_categories)s, %(image_url)s, %(source_modified_at)s, now())
        ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, body = EXCLUDED.body,
            published_at = EXCLUDED.published_at, content_hash = EXCLUDED.content_hash,
            source_categories = EXCLUDED.source_categories,
            image_url = COALESCE(EXCLUDED.image_url, articles.image_url),
            source_modified_at = COALESCE(EXCLUDED.source_modified_at, articles.source_modified_at),
            checked_at = now(),
            updated_at = CASE WHEN articles.content_hash <> EXCLUDED.content_hash
                OR articles.source_categories IS DISTINCT FROM EXCLUDED.source_categories
                THEN now() ELSE articles.updated_at END,
            content_changed_at = CASE WHEN %(meaningful)s THEN now() ELSE articles.content_changed_at END,
            change_count = articles.change_count + %(meaningful)s::int
    """
    stored = {
        r[0]: (r[1], r[2], r[3])
        for r in conn.execute(
            "SELECT url, title, body, content_hash FROM articles WHERE url = ANY(%s)", ([r["url"] for r in rows],)
        ).fetchall()
    }
    with conn.cursor() as cur:
        for row in rows:
            old = stored.get(row["url"])
            meaningful = is_meaningful(old, row)
            cur.execute(sql, {**row, "source_id": source_id, "meaningful": meaningful})
            if old is None:
                res.inserted += 1
            elif old[2] != row["content_hash"]:
                res.updated += 1
            res.changed += meaningful
            res.images += row["image_url"] is not None
            stored[row["url"]] = (row["title"], row["body"], row["content_hash"])
    conn.commit()


def scrape_wp(src: dict[str, Any], source_id: int, db_url: str, hours: int, fetcher: Fetcher, res: Result) -> None:
    base = src["base_url"].rstrip("/")
    api = f"{base}/wp-json/wp/v2/posts"
    category_names = fetch_categories(fetcher, base)
    after = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    total_pages = 1
    page = 1
    with psycopg.connect(db_url) as conn:
        while page <= min(total_pages, MAX_PAGES):
            params = {
                "after": after,
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "desc",
                "_fields": FIELDS,
                "_embed": "wp:featuredmedia",
            }
            resp = fetcher.get(api, params)
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            posts = resp.json()
            res.pages += 1
            rows = []
            for post in posts:
                try:
                    rows.append(map_post(post, category_names))
                except (KeyError, TypeError, ValueError) as e:
                    res.errors += 1
                    log.warning("%s: bad post %s: %r", res.domain, post.get("id"), e)
            res.posts += len(posts)
            upsert_articles(conn, source_id, rows, res)
            page += 1


def fetch_article_row(
    fetcher: Fetcher, res: Result, loc: str, url: str, title: str, published: datetime, entry: dict[str, Any]
) -> dict[str, Any] | None:
    """Fetch and extract one page; None if the page could not be read."""
    body = ""
    image = entry.get("image")
    try:
        html = fetcher.get(loc).text
        if is_challenge(html):
            raise ValueError("bot challenge")
        res.fetched += 1
        body = extract_body(html)
        image = image or extract_image(html, loc)
        if not body:
            res.failures += 1
    except (httpx.HTTPError, ValueError) as e:
        res.failures += 1
        log.debug("%s: %s: %r", res.domain, loc, e)
        return None
    return {
        "url": url,
        "external_id": None,
        "title": title,
        "body": body,
        "published_at": published,
        "content_hash": hashlib.sha256(f"{title}\n{body}".encode()).hexdigest(),
        "source_categories": url_categories(loc),
        "image_url": image,
        "source_modified_at": entry.get("lastmod"),
    }


def scrape_sitemap(
    src: dict[str, Any],
    source_id: int,
    db_url: str,
    hours: int,
    max_articles: int,
    refresh_hours: int,
    max_refresh: int,
    fetcher: Fetcher,
    res: Result,
) -> None:
    children, entries = parse_sitemap(fetcher.get(src["sitemap_url"]).content)
    for child in children[:MAX_CHILD_SITEMAPS]:
        entries.extend(parse_sitemap(fetcher.get(child).content)[1])
    by_url = {canonical_url(e["loc"]): e for e in entries}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    window = sorted((e for e in entries if e["published"] >= cutoff), key=lambda e: e["published"], reverse=True)
    window = window[:max_articles]
    res.posts = len(window)
    with psycopg.connect(db_url) as conn:
        urls = [canonical_url(e["loc"]) for e in window]
        stored = {
            r[0]
            for r in conn.execute("SELECT url FROM articles WHERE url = ANY(%s) AND body <> ''", (urls,)).fetchall()
        }
        for entry, url in zip(window, urls):
            if url in stored:
                continue
            row = fetch_article_row(fetcher, res, entry["loc"], url, entry["title"], entry["published"], entry)
            if row is None:
                row = {
                    "url": url,
                    "external_id": None,
                    "title": entry["title"],
                    "body": "",
                    "published_at": entry["published"],
                    "content_hash": hashlib.sha256(f"{entry['title']}\n".encode()).hexdigest(),
                    "source_categories": url_categories(entry["loc"]),
                    "image_url": entry.get("image"),
                    "source_modified_at": entry.get("lastmod"),
                }
            upsert_articles(conn, source_id, [row], res)
        due = conn.execute(
            """
            SELECT url, title, published_at FROM articles
            WHERE source_id = %s AND body <> '' AND published_at >= now() - make_interval(hours => %s)
                AND (checked_at IS NULL OR checked_at < now() - make_interval(mins => %s))
            ORDER BY published_at DESC LIMIT %s
            """,
            (source_id, refresh_hours, RECHECK_MINUTES, max_refresh),
        ).fetchall()
        base = urlsplit(src["base_url"])
        for url, stored_title, published in due:
            entry = by_url.get(url, {})
            parts = urlsplit(url)
            loc = entry.get("loc") or urlunsplit((base.scheme, base.netloc, parts.path, parts.query, ""))
            row = fetch_article_row(fetcher, res, loc, url, entry.get("title") or stored_title, published, entry)
            if row is None or not row["body"]:
                conn.execute("UPDATE articles SET checked_at = now() WHERE url = %s", (url,))
                conn.commit()
                continue
            res.refreshed += 1
            upsert_articles(conn, source_id, [row], res)


def scrape_source(
    src: dict[str, Any],
    source_id: int,
    db_url: str,
    hours: int,
    delay: float,
    ignore_robots: bool,
    max_articles: int,
    refresh_hours: int,
    max_refresh: int,
) -> Result:
    domain = src["domain"]
    res = Result(domain, method=src["method"])
    base = src["base_url"].rstrip("/")
    fetcher = Fetcher(delay)
    try:
        probe = f"{base}/wp-json/wp/v2/posts" if res.method == "wp_api" else src["sitemap_url"]
        if not ignore_robots and not robots_allowed(fetcher, base, probe):
            log.warning("%s: disallowed by robots.txt, skipping", domain)
            res.skipped = True
            return res
        if res.method == "wp_api":
            scrape_wp(src, source_id, db_url, hours, fetcher, res)
        elif res.method == "news_sitemap":
            scrape_sitemap(src, source_id, db_url, hours, max_articles, refresh_hours, max_refresh, fetcher, res)
        else:
            raise ValueError(f"unknown method {res.method!r}")
    except Exception as e:  # source failure must not stop others
        res.errors += 1
        log.error("%s: failed: %r", domain, e)
    finally:
        fetcher.client.close()
    return res


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db_url = os.environ["DATABASE_URL"]
    hours = int(os.environ.get("HOURS", "48"))
    delay = float(os.environ.get("REQUEST_DELAY_S", "2"))
    ignore_robots = os.environ.get("IGNORE_ROBOTS", "").lower() == "true"
    max_articles = int(os.environ.get("MAX_ARTICLES_PER_SOURCE", "150"))
    refresh_hours = int(os.environ.get("REFRESH_HOURS", "6"))
    max_refresh = int(os.environ.get("MAX_REFRESH_PER_SOURCE", "20"))
    only_edition = os.environ.get("EDITION", "")
    with open(os.environ.get("SOURCES_FILE", "/app/sources.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if ignore_robots:
        log.warning("robots.txt is ignored (IGNORE_ROBOTS=true, experiments only)")

    sources: list[dict[str, Any]] = []
    for code, edition in cfg["editions"].items():
        if only_edition and code != only_edition:
            continue
        sources.extend({**s, "language": edition.get("language", code)} for s in edition["sources"])
    if not sources:
        log.error("no sources selected (EDITION=%r)", only_edition)
        return 1
    ids: dict[str, int] = {}
    with psycopg.connect(db_url) as conn:
        for src in sources:
            row = conn.execute(
                """
                INSERT INTO sources (name, domain, base_url, language) VALUES (%s, %s, %s, %s)
                ON CONFLICT (domain) DO UPDATE SET name = EXCLUDED.name, base_url = EXCLUDED.base_url,
                    language = EXCLUDED.language
                RETURNING id
                """,
                (src["name"], src["domain"], src["base_url"], src["language"]),
            ).fetchone()
            assert row is not None
            ids[src["domain"]] = row[0]

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = [
            pool.submit(
                scrape_source,
                s,
                ids[s["domain"]],
                db_url,
                hours,
                delay,
                ignore_robots,
                max_articles,
                refresh_hours,
                max_refresh,
            )
            for s in sources
        ]
        results = [f.result() for f in futures]

    for r in results:
        log.info(
            "%s: method=%s pages=%d in_window=%d fetched=%d extraction_failures=%d inserted=%d updated=%d "
            "images=%d changed=%d refreshed=%d errors=%d%s",
            r.domain,
            r.method,
            r.pages,
            r.posts,
            r.fetched,
            r.failures,
            r.inserted,
            r.updated,
            r.images,
            r.changed,
            r.refreshed,
            r.errors,
            " skipped" if r.skipped else "",
        )
    log.info(
        "TOTAL: sources=%d pages=%d posts=%d inserted=%d updated=%d changed=%d refreshed=%d errors=%d " "in %.0fs",
        len(results),
        sum(r.pages for r in results),
        sum(r.posts for r in results),
        sum(r.inserted for r in results),
        sum(r.updated for r in results),
        sum(r.changed for r in results),
        sum(r.refreshed for r in results),
        sum(r.errors for r in results),
        time.monotonic() - start,
    )
    failed = all(r.errors and not r.pages for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
