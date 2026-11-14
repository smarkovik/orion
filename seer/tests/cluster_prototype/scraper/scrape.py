"""Scrape recent posts from WordPress news sites into Postgres."""

import hashlib
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import psycopg
import yaml

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
MAX_PAGES = 10
RETRIES = 2
FIELDS = "id,date_gmt,link,title,content,categories"
DROP_PARAMS = ("utm_", "at_")
DROP_EXACT = {"fbclid", "gclid"}
BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "figure"}
SKIP_TAGS = {"script", "style"}

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


@dataclass
class Result:
    domain: str
    pages: int = 0
    posts: int = 0
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


def scrape_source(
    src: dict[str, Any], source_id: int, db_url: str, hours: int, delay: float, ignore_robots: bool
) -> Result:
    domain = src["domain"]
    res = Result(domain)
    base = src["base_url"].rstrip("/")
    api = f"{base}/wp-json/wp/v2/posts"
    fetcher = Fetcher(delay)
    try:
        if not ignore_robots and not robots_allowed(fetcher, base, api):
            log.warning("%s: disallowed by robots.txt, skipping", domain)
            res.skipped = True
            return res
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
                        log.warning("%s: bad post %s: %r", domain, post.get("id"), e)
                res.posts += len(posts)
                ins, upd = upsert_articles(conn, source_id, rows)
                res.inserted += ins
                res.updated += upd
                page += 1
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
    with open(os.environ.get("SOURCES_FILE", "/app/sources.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    language = cfg.get("language", "mk")
    if ignore_robots:
        log.warning("robots.txt is ignored (IGNORE_ROBOTS=true, experiments only)")

    sources = cfg["sources"]
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
                (src["name"], src["domain"], src["base_url"], language),
            ).fetchone()
            assert row is not None
            ids[src["domain"]] = row[0]

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = [
            pool.submit(scrape_source, s, ids[s["domain"]], db_url, hours, delay, ignore_robots) for s in sources
        ]
        results = [f.result() for f in futures]

    for r in results:
        log.info(
            "%s: pages=%d posts=%d inserted=%d updated=%d errors=%d%s",
            r.domain,
            r.pages,
            r.posts,
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
