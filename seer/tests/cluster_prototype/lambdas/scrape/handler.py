"""Fetch recent articles (WordPress API or news sitemap) for one edition into one raw S3 object."""

import logging
import os
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from seer_common import store
from seer_common.text import absolute_image, canonical_url, html_to_text, parse_utc

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
MAX_PAGES = 10
MAX_CHILD_SITEMAPS = 5
RETRIES = 2
MIN_REMAINING_S = 60
MODIFIED_OVERLAP = timedelta(minutes=10)
FIELDS = "id,date_gmt,modified_gmt,link,title,content,categories,jetpack_featured_media_url,_links,_embedded"

logging.getLogger().setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("scrape")


@dataclass
class Config:
    edition: str
    hours: int
    delay: float
    ignore_robots: bool
    max_articles: int
    refresh_hours: int
    max_refresh: int
    recheck_minutes: int
    deadline: float | None
    state: dict[str, Any]
    truncated: threading.Event = field(default_factory=threading.Event)
    writer: store.JsonlGzWriter = field(default_factory=store.JsonlGzWriter)

    def out_of_time(self) -> bool:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.truncated.set()
        return self.truncated.is_set()


@dataclass
class Result:
    domain: str
    method: str
    listed: int = 0
    fetched: int = 0
    refresh: int = 0
    failures: int = 0
    errors: int = 0
    skipped: bool = False
    records: int = 0

    def manifest(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "listed": self.listed,
            "fetched": self.fetched,
            "refresh": self.refresh,
            "failures": self.failures,
            "errors": self.errors,
            "skipped": self.skipped,
        }


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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def fetch_categories(fetcher: Fetcher, base: str) -> dict[str, str]:
    names: dict[str, str] = {}
    page, total = 1, 1
    while page <= min(total, MAX_PAGES):
        resp = fetcher.get(f"{base}/wp-json/wp/v2/categories", {"per_page": 100, "page": page, "_fields": "id,name"})
        total = int(resp.headers.get("X-WP-TotalPages", 1))
        names.update({str(c["id"]): html_to_text(c["name"], keep_breaks=False) for c in resp.json()})
        page += 1
    return names


def last_ok(cfg: Config, domain: str) -> datetime | None:
    raw = ((cfg.state.get("sources") or {}).get(domain) or {}).get("last_ok_started_at")
    return parse_utc(raw) if isinstance(raw, str) else None


def scrape_wp(src: dict[str, Any], cfg: Config, fetcher: Fetcher, res: Result) -> None:
    base = src["base_url"].rstrip("/")
    api = f"{base}/wp-json/wp/v2/posts"
    category_names = fetch_categories(fetcher, base)
    fmt = "%Y-%m-%dT%H:%M:%S"
    params: dict[str, Any] = {
        "after": (datetime.now(timezone.utc) - timedelta(hours=cfg.hours)).strftime(fmt),
        "per_page": 100,
        "orderby": "date",
        "order": "desc",
        "_fields": FIELDS,
        "_embed": "wp:featuredmedia",
    }
    since = last_ok(cfg, res.domain)
    cutoff = since - MODIFIED_OVERLAP if since is not None else None
    if cutoff is not None:
        params["modified_after"] = cutoff.strftime(fmt)
    total_pages, page = 1, 1
    while page <= min(total_pages, MAX_PAGES):
        if cfg.out_of_time():
            break
        params["page"] = page
        try:
            resp = fetcher.get(api, params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 400 or "modified_after" not in params:
                raise
            del params["modified_after"]
            resp = fetcher.get(api, params)
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        posts = resp.json()
        res.listed += len(posts)
        res.fetched += 1
        fetched_at = now_iso()
        for post in posts:
            # Some older WordPress versions ignore modified_after.
            modified = parse_utc(post.get("modified_gmt"))
            if cutoff is not None and modified is not None and modified < cutoff:
                continue
            wanted = {str(c): category_names[str(c)] for c in post.get("categories", []) if str(c) in category_names}
            link = post.get("link") or ""
            res.records += 1
            cfg.writer.add(
                {
                    "v": 1,
                    "kind": "wp_post",
                    "edition": cfg.edition,
                    "source": res.domain,
                    "fetched_at": fetched_at,
                    "url": canonical_url(link) if link else None,
                    "loc": link,
                    "status": resp.status_code,
                    "payload": post,
                    "meta": {"categories": wanted},
                }
            )
        page += 1


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(xml: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (child sitemap URLs, entries with loc/title/published/image/lastmod) from a sitemap or index."""
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
        published = parse_utc(fields.get("publication_date"))
        if not fields.get("loc") or published is None:
            continue
        entries.append(
            {
                "loc": fields["loc"],
                "title": html_to_text(fields.get("title", ""), keep_breaks=False),
                "published": published,
                "image": absolute_image(image, fields["loc"]),
                "lastmod": parse_utc(fields.get("lastmod")),
            }
        )
    return children, entries


def is_challenge(html: str) -> bool:
    head = html[:3000]
    return "Just a moment" in head or "dd={" in head


def fetch_page(
    cfg: Config, fetcher: Fetcher, res: Result, loc: str, url: str, entry: dict[str, Any], refresh: bool
) -> None:
    rec: dict[str, Any] = {
        "v": 1,
        "kind": "html",
        "edition": cfg.edition,
        "source": res.domain,
        "fetched_at": now_iso(),
        "url": url,
        "loc": loc,
        "status": 0,
        "meta": {
            "title": entry.get("title"),
            "published": entry["published"].isoformat() if entry.get("published") else None,
            "image": entry.get("image"),
            "lastmod": entry["lastmod"].isoformat() if entry.get("lastmod") else None,
            "refresh": refresh,
        },
    }
    try:
        resp = fetcher.get(loc)
        rec["status"] = resp.status_code
        if is_challenge(resp.text):
            rec["error"] = "bot challenge"
        else:
            rec["html"] = resp.text
    except httpx.HTTPStatusError as e:
        rec["status"] = e.response.status_code
        rec["error"] = f"HTTP {e.response.status_code}"
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        rec["error"] = type(e).__name__
    if "error" in rec:
        res.failures += 1
        log.debug("%s: %s: %s", res.domain, loc, rec["error"])
    else:
        res.fetched += 1
    res.refresh += refresh
    res.records += 1
    cfg.writer.add(rec)


def scrape_sitemap(src: dict[str, Any], cfg: Config, fetcher: Fetcher, res: Result) -> None:
    children, entries = parse_sitemap(fetcher.get(src["sitemap_url"]).content)
    for child in children[:MAX_CHILD_SITEMAPS]:
        entries.extend(parse_sitemap(fetcher.get(child).content)[1])
    by_url = {canonical_url(e["loc"]): e for e in entries}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=cfg.hours)
    window = sorted((e for e in entries if e["published"] >= cutoff), key=lambda e: e["published"], reverse=True)
    window = window[: cfg.max_articles]
    res.listed = len(window)
    known: dict[str, dict[str, Any]] = ((cfg.state.get("sources") or {}).get(res.domain) or {}).get("known") or {}
    for entry in window:
        url = canonical_url(entry["loc"])
        if (known.get(url) or {}).get("b"):
            continue
        if cfg.out_of_time():
            return
        fetch_page(cfg, fetcher, res, entry["loc"], url, entry, False)

    refresh_cutoff = now - timedelta(hours=cfg.refresh_hours)
    recheck_cutoff = now - timedelta(minutes=cfg.recheck_minutes)
    due: list[tuple[datetime, str]] = []
    for url, k in known.items():
        published, checked = parse_utc(k.get("p")), parse_utc(k.get("c"))
        if k.get("b") and published and published >= refresh_cutoff and (checked is None or checked < recheck_cutoff):
            due.append((published, url))
    due.sort(reverse=True)
    base = urlsplit(src["base_url"])
    for published, url in due[: cfg.max_refresh]:
        if cfg.out_of_time():
            return
        entry = by_url.get(url, {})
        parts = urlsplit(url)
        loc = entry.get("loc") or urlunsplit((base.scheme, base.netloc, parts.path, parts.query, ""))
        meta = {**entry, "published": entry.get("published") or published}
        fetch_page(cfg, fetcher, res, loc, url, meta, True)


def scrape_source(src: dict[str, Any], cfg: Config) -> Result:
    domain = src["domain"]
    res = Result(domain, src["method"])
    base = src["base_url"].rstrip("/")
    fetcher = Fetcher(cfg.delay)
    try:
        probe = f"{base}/wp-json/wp/v2/posts" if res.method == "wp_api" else src["sitemap_url"]
        if not cfg.ignore_robots and not robots_allowed(fetcher, base, probe):
            log.warning("%s: disallowed by robots.txt, skipping", domain)
            res.skipped = True
            return res
        if res.method == "wp_api":
            scrape_wp(src, cfg, fetcher, res)
        elif res.method == "news_sitemap":
            scrape_sitemap(src, cfg, fetcher, res)
        else:
            raise ValueError(f"unknown method {res.method!r}")
    except Exception as e:  # source failure must not stop others
        res.errors += 1
        log.error("%s: failed: %r", domain, e)
    finally:
        fetcher.client.close()
    return res


def remaining_deadline(context: Any) -> float | None:
    try:
        return time.monotonic() + context.get_remaining_time_in_millis() / 1000 - MIN_REMAINING_S
    except Exception:
        return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    t0 = time.monotonic()
    started = datetime.now(timezone.utc)
    edition = event["edition"]
    env = os.environ
    with open(env.get("SOURCES_FILE", "/var/task/sources.yaml"), encoding="utf-8") as f:
        editions = yaml.safe_load(f)["editions"]
    if edition not in editions:
        raise ValueError(f"unknown edition {edition!r}")
    sources = editions[edition]["sources"]
    ignore_robots = env.get("IGNORE_ROBOTS", "").lower() == "true"
    if ignore_robots:
        log.warning("robots.txt is ignored (IGNORE_ROBOTS=true, experiments only)")
    cfg = Config(
        edition=edition,
        hours=int(event.get("hours") or env.get("HOURS", "48")),
        delay=float(env.get("REQUEST_DELAY_S", "2")),
        ignore_robots=ignore_robots,
        max_articles=int(env.get("MAX_ARTICLES_PER_SOURCE", "150")),
        refresh_hours=int(env.get("REFRESH_HOURS", "6")),
        max_refresh=int(env.get("MAX_REFRESH_PER_SOURCE", "20")),
        recheck_minutes=int(env.get("RECHECK_MINUTES", "60")),
        deadline=remaining_deadline(context),
        state=store.get_json(store.RAW_BUCKET, store.state_key(edition), gz=True) or {},
    )
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        results = list(pool.map(lambda s: scrape_source(s, cfg), sources))

    for r in results:
        log.info(
            "%s: method=%s listed=%d fetched=%d refresh=%d failures=%d errors=%d%s",
            r.domain,
            r.method,
            r.listed,
            r.fetched,
            r.refresh,
            r.failures,
            r.errors,
            " skipped" if r.skipped else "",
        )
    run_id = store.run_id_for(started, edition)
    raw_key = store.raw_key(edition, started, run_id)
    manifest_key = store.manifest_key(edition, run_id)
    records, bytes_raw, bytes_gz = cfg.writer.upload(store.RAW_BUCKET, raw_key)
    manifest = {
        "run_id": run_id,
        "edition": edition,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": now_iso(),
        "raw_key": raw_key,
        "records": records,
        "bytes_raw": bytes_raw,
        "bytes_gz": bytes_gz,
        "truncated": cfg.truncated.is_set(),
        "sources": {r.domain: r.manifest() for r in results},
    }
    store.put_json(store.RAW_BUCKET, manifest_key, manifest)
    duration = round(time.monotonic() - t0, 1)
    log.info(
        "TOTAL: edition=%s sources=%d records=%d bytes_raw=%d bytes_gz=%d errors=%d truncated=%s in %.1fs",
        edition,
        len(results),
        records,
        bytes_raw,
        bytes_gz,
        sum(r.errors for r in results),
        cfg.truncated.is_set(),
        duration,
    )
    if all(r.errors and not r.records for r in results):
        raise RuntimeError(f"every source failed for edition {edition}")
    return {
        "edition": edition,
        "run_id": run_id,
        "started_at": manifest["started_at"],
        "raw_key": raw_key,
        "manifest_key": manifest_key,
        "records": records,
        "bytes_raw": bytes_raw,
        "bytes_gz": bytes_gz,
        "truncated": manifest["truncated"],
        "sources": manifest["sources"],
        "duration_s": duration,
    }
