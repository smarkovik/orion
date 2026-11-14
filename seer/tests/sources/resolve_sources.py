"""Resolve TIME.mk source names to outlet websites and RSS feeds. Prototype.

A domain counts as verified only when the fetched homepage's title or site name matches the outlet name.
Run: python resolve_sources.py ../../docs/timemk-sources.csv ../../docs/sources.csv
"""

import csv
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import httpx

UA = "Mozilla/5.0 (compatible; SeerResearch/0.1)"
FEED_PROBES = ["/feed/", "/rss", "/rss.xml", "/feed.xml"]

# Candidates where the TIME.mk slug doesn't spell the domain. Unverified until fetched.
HINTS = {
    "24vesti": ["24.mk"],
    "tv21": ["tv21.tv"],
    "nova_mk": ["novamakedonija.com.mk"],
    "dw": ["www.dw.com/mk"],
    "bloomberg": ["bloombergadria.com/mk", "mk.bloombergadria.com"],
    "prizma": ["prizma.mk", "prizma.birn.eu.com"],
    "civil": ["civilmedia.mk"],
    "vecer": ["vecer.press"],
    "vecermk": ["vecer.mk"],
    "vocentar": ["vocentar.com"],
    "48chasa": ["48casa.mk", "48chasa.mk"],
    "kajgana": ["kajgana.com"],
    "crnobelo": ["crnobelo.com"],
    "itcom": ["it.mk"],
    "taratur": ["taratur.com.mk"],
    "365": ["365.com.mk"],
    "drmitov": ["drmitov.mk", "doktormitov.mk"],
    "avtomagazin": ["avtomagazin.com.mk"],
    "ev": ["e-avtomobili.mk", "ev.mk"],
    "ohridpress": ["ohridpress.com.mk", "ohridpress.mk"],
    "makfudbal": ["makfudbal.com"],
    "sportmania": ["sportmanija.mk", "sportmania.mk"],
    "sportmedia": ["sportsport.mk", "sportmedia.mk"],
    "ilinden": ["vesnik-ilinden.com"],
}

# Names the outlet uses on its own site, when it differs from TIME.mk's label.
ALIASES = {
    "24 Вести": ["Телевизија 24", "24.mk"],
    "Bloomberg Adria": ["Блумберг Адрија"],
    "Frontline": ["Прва линија"],
    "Битола Њуз": ["Bitola News"],
}
# Checked by hand: the page never names the outlet (DW's title is "Теми").
MANUAL = {"dw": "https://www.dw.com/mk"}
PARKED = re.compile(r"for sale|buy this domain|domain is parked", re.I)
MK_ONLY_LETTERS = re.compile(r"[ѓќѕЃЌЅ]")
CYR = dict(
    zip(
        "абвгдѓежзѕијклљмнњопрстќуфхцчџш",
        "a b v g d gj e zh z dz i j k l lj m n nj o p r s t kj u f h c ch dzh sh".split(),
    )
)
PLAIN = {"gj": "g", "zh": "z", "dz": "z", "kj": "k", "ch": "c", "dzh": "dz", "sh": "s"}


def variants(text: str) -> set[str]:
    low = text.lower()
    full = "".join(CYR.get(c, c) for c in low)
    plain = "".join(PLAIN.get(CYR.get(c, ""), CYR.get(c, c)) for c in low)
    return {re.sub(r"[^\w]", "", v) for v in (low, full, plain)}


def name_matches(name: str, haystack: str) -> bool:
    tokens = [t for t in re.split(r"[\s.]+", name) if len(t) >= 2 and not t.endswith(".")]
    hay = variants(haystack)
    return all(any(v and v in h for v in variants(t) for h in hay) for t in tokens)


def decode(resp: httpx.Response) -> str:
    if resp.charset_encoding:
        return resp.text
    for enc in ("utf-8", "cp1251"):
        try:
            return resp.content.decode(enc)
        except UnicodeDecodeError:
            continue
    return resp.content.decode("utf-8", "replace")


def meta(page: str) -> tuple[str, str]:
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    site = re.search(r'property=["\']og:site_name["\'][^>]*content=["\']([^"\']*)', page, re.I)
    clean = lambda m: html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""  # noqa: E731
    return clean(title), clean(site)


def fetch(client: httpx.Client, url: str, tries: int = 2) -> httpx.Response | None:
    for _ in range(tries):
        try:
            return client.get(url)
        except httpx.HTTPError:
            continue
    return None


def is_cloudflare_challenge(resp: httpx.Response) -> bool:
    return resp.status_code in (403, 503) and "Just a moment" in resp.text[:2000]


def feed_age_days(latest: str) -> int | None:
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(latest)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def check_feed(client: httpx.Client, url: str) -> dict | None:
    r = fetch(client, url)
    if r is None or r.status_code != 200:
        return None
    body = decode(r)
    if not re.search(r"<(rss|feed|rdf:RDF)[\s>]", body[:3000]):
        return None
    latest = re.search(r"<(pubDate|updated|dc:date)>([^<]+)<", body)
    items = body.count("<item") + body.count("<entry")
    age = feed_age_days(latest.group(2).strip()) if latest else None
    return {"rss_url": str(r.url), "rss_items": items, "rss_age_days": "" if age is None else age}


def find_feed(client: httpx.Client, base: str, page: str) -> dict | None:
    links = re.findall(r"<link[^>]+>", page, re.I)
    feeds = [
        html.unescape(m.group(1))
        for tag in links
        if re.search(r"application/(rss|atom)\+xml", tag, re.I)
        for m in [re.search(r'href=["\']([^"\']+)', tag)]
        if m and "comment" not in m.group(1).lower()
    ]
    for url in [urljoin(base, f) for f in feeds] + [urljoin(base, p) for p in FEED_PROBES]:
        found = check_feed(client, url)
        if found:
            return found
    return None


def resolve(row: dict) -> dict:
    slug = row["timemk_slug"].replace("_", "")
    candidates = HINTS.get(row["timemk_slug"], []) + [f"{slug}.mk", f"{slug}.com.mk", f"{slug}.com"]
    names = [row["name"]] + ALIASES.get(row["name"], [])
    best: dict = {}
    blocked = ""
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=12) as client:
        if row["timemk_slug"] in MANUAL:
            r = fetch(client, MANUAL[row["timemk_slug"]])
            page = decode(r) if r is not None else ""
            best = {"website": MANUAL[row["timemk_slug"]], "match": "manual", "title": meta(page)[0], "page": page}
            candidates = []
        for cand in dict.fromkeys(candidates):
            r = fetch(client, f"https://{cand}") or fetch(client, f"http://{cand}", tries=1)
            if r is None:
                continue
            if is_cloudflare_challenge(r):
                blocked = blocked or str(r.url)
                continue
            if r.status_code >= 400:
                continue
            page = decode(r)
            title, site = meta(page)
            host = urlparse(str(r.url)).netloc.removeprefix("www.")
            if len(page) < 1000 or PARKED.search(f"{title} {page[:5000]}"):
                continue
            if not (host.endswith(".mk") or MK_ONLY_LETTERS.search(page) or re.search(r"<html[^>]+lang=.mk", page)):
                continue
            if any(name_matches(n, f"{title} {site}") for n in names):
                match = "title"
            elif any(name_matches(n, host) for n in names):
                match = "domain"
            else:
                continue
            if not best or (match == "title" and best["match"] == "domain"):
                best = {"website": str(r.url), "match": match, "title": title or site, "page": page}
            if match == "title":
                break
        if best:
            best.update(find_feed(client, best["website"], best.pop("page")) or {})
        elif blocked:
            best = {"website": blocked, "match": "blocked"}
    return {**row, **best}


def main(src: str, dst: str) -> None:
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(resolve, rows))
    fields = ["group", "name", "timemk_slug", "website", "match", "title", "rss_url", "rss_items", "rss_age_days"]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    summary = {
        "sources": len(results),
        "website_title_match": sum(r.get("match") == "title" for r in results),
        "website_domain_match": sum(r.get("match") == "domain" for r in results),
        "blocked_by_cloudflare": sum(r.get("match") == "blocked" for r in results),
        "unresolved": sum(not r.get("website") for r in results),
        "with_rss": sum(bool(r.get("rss_url")) for r in results),
        "rss_fresh_7d": sum(r.get("rss_age_days") not in (None, "") and r["rss_age_days"] <= 7 for r in results),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
