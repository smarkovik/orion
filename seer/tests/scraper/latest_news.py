"""List a news site's latest articles. Prototype, language-agnostic.

Order of attempts: RSS/Atom feed -> homepage links via plain HTTP -> homepage via Lightpanda (JS pages).
HTML links have no dates, so the top candidates are fetched and their published time read from metadata.

Run: python latest_news.py https://sdk.mk https://www.lemonde.fr --limit 10 [--html] [--json]
Lightpanda: set LIGHTPANDA_BIN or put `lightpanda` on PATH.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx

UA = "Mozilla/5.0 (compatible; SeerResearch/0.1)"
FEED_PROBES = ["/feed/", "/rss", "/rss.xml", "/feed.xml"]
MIN_HTML_LINKS = 5
SKIP_PATH = re.compile(
    r"/(tags?|category|categories|categorie|rubrique|author|auteur|page|search|recherche|login|connexion|account|"
    r"compte|abonnement|newsletters?|contact|about|privacy|cookies|services|jeux|meteo|dossier)(/|$)",
    re.I,
)
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp|pdf|xml|css|js|mp3|mp4)$", re.I)
# An ID or a date in the path is a strong article signal (lemonde _6810346, figaro -20261114, /2026/11/14/).
STRONG_PATH = re.compile(r"\d{5,}|/20\d{2}/\d{2}/|20\d{6}")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-", re.I)
URL_DATE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/|(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
DATE_PATTERNS = [
    r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',
    r'content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time',
    r'"datePublished"\s*:\s*"([^"]+)"',
    r'itemprop=["\']datePublished["\'][^>]*(?:content|datetime)=["\']([^"\']+)',
]


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def parse_date(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def url_date(path: str) -> datetime | None:
    m = URL_DATE.search(path)
    if not m:
        return None
    y, mo, d = (int(g) for g in (m.groups()[:3] if m.group(1) else m.groups()[3:]))
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def robots_for(client: httpx.Client, site: str) -> RobotFileParser:
    rp = RobotFileParser()
    try:
        r = client.get(urljoin(site, "/robots.txt"))
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        rp.parse([])
    return rp


def block_reason(r: httpx.Response) -> str:
    if r.status_code < 400:
        return ""
    body = r.text[:3000]
    if "Just a moment" in body:
        return "Cloudflare bot check"
    if "dd={" in body or "datadome" in body.lower():
        return "DataDome bot check"
    return f"HTTP {r.status_code}"


def from_feed(client: httpx.Client, site: str, page: str) -> list[dict]:
    tags = re.findall(r"<link[^>]+>", page, re.I)
    advertised = [
        html.unescape(m.group(1))
        for t in tags
        if re.search(r"application/(rss|atom)\+xml", t, re.I)
        for m in [re.search(r'href=["\']([^"\']+)', t)]
        if m and "comment" not in m.group(1).lower()
    ]
    for url in [urljoin(site, u) for u in advertised] + [urljoin(site, p) for p in FEED_PROBES]:
        try:
            r = client.get(url)
        except httpx.HTTPError:
            continue
        if r.status_code != 200:
            continue
        feed = feedparser.parse(r.content)
        items = []
        for e in feed.entries:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            items.append(
                {
                    "title": html.unescape(e.get("title", "")).strip(),
                    "url": e.get("link", ""),
                    "published": datetime(*ts[:6], tzinfo=timezone.utc) if ts else None,
                }
            )
        if items:
            return items
    return []


def article_links(site: str, page: str) -> list[dict]:
    site_host, seen, out = host_of(site), {}, []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page, re.S | re.I):
        url = urljoin(site, html.unescape(m.group(1))).split("?")[0]
        if host_of(url) != site_host:
            continue
        path = unquote(urlparse(url).path).rstrip("/")
        if not path or SKIP_PATH.search(path) or SKIP_EXT.search(path):
            continue
        strong = bool(STRONG_PATH.search(path)) and not UUID.search(path)
        if path.split("/")[-1].count("-") < 3 and not strong:
            continue
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if url in seen:
            if len(text) > len(out[seen[url]]["title"]):
                out[seen[url]]["title"] = text
            continue
        seen[url] = len(out)
        out.append({"title": text, "url": url, "published": None, "strong": strong, "url_date": url_date(path)})
    strong_only = [i for i in out if i["strong"]]
    links = strong_only if len(strong_only) >= MIN_HTML_LINKS else out
    # Dated URLs first (newest day first), the rest keep homepage order.
    return sorted(links, key=lambda i: -i["url_date"].timestamp() if i["url_date"] else float("inf"))


def lightpanda_html(url: str) -> str:
    binary = os.environ.get("LIGHTPANDA_BIN") or shutil.which("lightpanda")
    if not binary:
        return ""
    run = subprocess.run(
        [binary, "fetch", "--dump", "html", "--obey-robots", "--wait-ms", "5000", url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return run.stdout


def add_dates(client: httpx.Client, items: list[dict]) -> None:
    def probe(item: dict) -> None:
        try:
            page = client.get(item["url"]).text
        except httpx.HTTPError:
            return
        for pattern in DATE_PATTERNS:
            m = re.search(pattern, page, re.I)
            if m and (dt := parse_date(m.group(1))):
                item["published"] = dt
                break
        if not item["title"] and (t := re.search(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)', page)):
            item["title"] = html.unescape(t.group(1))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(probe, items))


def latest(site: str, limit: int, force_html: bool) -> dict:
    result = {"site": site, "method": "", "items": [], "note": ""}
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=15) as client:
        try:
            home = client.get(site)
        except httpx.HTTPError as e:
            result.update(method="failed", note=type(e).__name__)
            return result
        if reason := block_reason(home):
            result.update(method="blocked", note=reason)
            return result
        site = str(home.url)
        rp = robots_for(client, site)
        if not rp.can_fetch(UA, site):
            result.update(method="disallowed", note="robots.txt disallows this crawler")
            return result
        items = [] if force_html else from_feed(client, site, home.text)
        result["method"] = "rss"
        if not items:
            items, result["method"] = article_links(site, home.text), "html"
            if len(items) < MIN_HTML_LINKS:
                items, result["method"] = article_links(site, lightpanda_html(site)), "lightpanda"
            items = [i for i in items if rp.can_fetch(UA, i["url"])][: limit * 3]
            add_dates(client, items)
            for i in items:
                i["published"] = i["published"] or i["url_date"]
    dated = sorted((i for i in items if i["published"]), key=lambda i: i["published"], reverse=True)
    undated = [i for i in items if not i["published"]]
    result["items"] = (dated + undated)[:limit]
    result["note"] = f"{len(dated)} of {len(items)} candidates dated; undated keep homepage order"
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="+")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--html", action="store_true", help="skip RSS, test the HTML path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda s: latest(s, args.limit, args.html), args.sites))
    for res in results:
        if args.json:
            print(json.dumps(res, default=str, ensure_ascii=False))
            continue
        print(f"\n## {res['site']} · {res['method']} · {len(res['items'])} items · {res['note']}", file=sys.stdout)
        for i in res["items"]:
            when = i["published"].strftime("%Y-%m-%d %H:%M") if i["published"] else "undated".ljust(16)
            print(f"  {when}  {i['title'][:70]:70}  {i['url']}")


if __name__ == "__main__":
    main()
