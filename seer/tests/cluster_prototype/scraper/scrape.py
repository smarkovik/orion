"""Scrape recent articles (WordPress API or news sitemap) into Postgres."""

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
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import psycopg
import trafilatura
import yaml

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
MAX_PAGES = 10
MAX_CHILD_SITEMAPS = 5
RETRIES = 2
FIELDS = "id,date_gmt,link,title,content,categories"
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
        for el in node.iter():
            fields.setdefault(local_name(el.tag), (el.text or "").strip())
        if kind == "sitemap":
            if fields.get("loc"):
                children.append(fields["loc"])
            continue
        raw_date = fields.get("publication_date")
        if not fields.get("loc") or not raw_date:
            continue
        try:
            published = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        title = html_to_text(fields.get("title", ""), keep_breaks=False)
        entries.append({"loc": fields["loc"], "title": title, "published": published.astimezone(timezone.utc)})
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


def upsert_articles(conn: psycopg.Connection, source_id: int, rows: list[dict[str, Any]]) -> tuple[int, int]:
    ins = upd = 0
    sql = """
        INSERT INTO articles (source_id, url, external_id, title, body, published_at, content_hash, source_categories)
        VALUES (%(source_id)s, %(url)s, %(external_id)s, %(title)s, %(body)s, %(published_at)s, %(content_hash)s,
                %(source_categories)s)
        ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, body = EXCLUDED.body,
            published_at = EXCLUDED.published_at, content_hash = EXCLUDED.content_hash,
            source_categories = EXCLUDED.source_categories, updated_at = now()
        WHERE articles.content_hash <> EXCLUDED.content_hash
            OR articles.source_categories IS DISTINCT FROM EXCLUDED.source_categories
        RETURNING (xmax = 0) AS inserted
    """
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, {**row, "source_id": source_id})
            res = cur.fetchone()
            if res is not None:
                ins, upd = (ins + 1, upd) if res[0] else (ins, upd + 1)
    conn.commit()
    return ins, upd


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
            ins, upd = upsert_articles(conn, source_id, rows)
            res.inserted += ins
            res.updated += upd
            page += 1


def scrape_sitemap(
    src: dict[str, Any], source_id: int, db_url: str, hours: int, max_articles: int, fetcher: Fetcher, res: Result
) -> None:
    children, entries = parse_sitemap(fetcher.get(src["sitemap_url"]).content)
    for child in children[:MAX_CHILD_SITEMAPS]:
        entries.extend(parse_sitemap(fetcher.get(child).content)[1])
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
            body = ""
            try:
                html = fetcher.get(entry["loc"]).text
                if is_challenge(html):
                    raise ValueError("bot challenge")
                res.fetched += 1
                body = extract_body(html)
                if not body:
                    res.failures += 1
            except (httpx.HTTPError, ValueError) as e:
                res.failures += 1
                log.debug("%s: %s: %r", res.domain, entry["loc"], e)
            row = {
                "url": url,
                "external_id": None,
                "title": entry["title"],
                "body": body,
                "published_at": entry["published"],
                "content_hash": hashlib.sha256(f"{entry['title']}\n{body}".encode()).hexdigest(),
                "source_categories": url_categories(entry["loc"]),
            }
            ins, upd = upsert_articles(conn, source_id, [row])
            res.inserted += ins
            res.updated += upd


def scrape_source(
    src: dict[str, Any], source_id: int, db_url: str, hours: int, delay: float, ignore_robots: bool, max_articles: int
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
            scrape_sitemap(src, source_id, db_url, hours, max_articles, fetcher, res)
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
            pool.submit(scrape_source, s, ids[s["domain"]], db_url, hours, delay, ignore_robots, max_articles)
            for s in sources
        ]
        results = [f.result() for f in futures]

    for r in results:
        log.info(
            "%s: method=%s pages=%d in_window=%d fetched=%d extraction_failures=%d inserted=%d updated=%d errors=%d%s",
            r.domain,
            r.method,
            r.pages,
            r.posts,
            r.fetched,
            r.failures,
            r.inserted,
            r.updated,
            r.errors,
            " skipped" if r.skipped else "",
        )
    log.info(
        "TOTAL: sources=%d pages=%d posts=%d inserted=%d updated=%d errors=%d in %.0fs",
        len(results),
        sum(r.pages for r in results),
        sum(r.posts for r in results),
        sum(r.inserted for r in results),
        sum(r.updated for r in results),
        sum(r.errors for r in results),
        time.monotonic() - start,
    )
    failed = all(r.errors and not r.pages for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
