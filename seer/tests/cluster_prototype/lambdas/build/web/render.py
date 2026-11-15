"""Public site pages: pure functions of the window and the site settings."""

import calendar
import hashlib
import html
import posixpath
from datetime import date, datetime, timedelta
from email.utils import format_datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, NamedTuple
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from model import Story, Window

HERE = Path(__file__).parent
GRID = 12  # cards before the plain list of further titles
NEW_HOURS = 3
UPDATED_HOURS = 6
HTML = "text/html; charset=utf-8"
ASSET_CACHE = "public, max-age=31536000, immutable"


class Page(NamedTuple):
    key: str
    body: bytes
    content_type: str
    cache_control: str


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(HERE / "templates")), autoescape=True, trim_blocks=True, lstrip_blocks=True
    )


@lru_cache(maxsize=1)
def _assets() -> dict[str, tuple[str, bytes, str]]:
    out = {}
    for ext, ctype in (("css", "text/css; charset=utf-8"), ("js", "text/javascript; charset=utf-8")):
        body = (HERE / "static" / f"site.{ext}").read_bytes()
        out[ext] = (f"assets/site.{hashlib.sha1(body).hexdigest()[:10]}.{ext}", body, ctype)
    return out


def render_assets() -> tuple[list[Page], str, str]:
    a = _assets()
    pages = [Page(key, body, ctype, ASSET_CACHE) for key, body, ctype in (a["css"], a["js"])]
    return pages, a["css"][0], a["js"][0]


def _ed(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["editions"][cfg["edition"]]


def _tz(cfg: dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(_ed(cfg)["timezone"])


def _seq(s: Story) -> int:
    tail = s.id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _eligible(window: Window, cfg: dict[str, Any]) -> list[Story]:
    low = cfg["limits"]["min_sources"]
    return [s for s in window.stories.values() if s.source_count >= low and s.label_url in window.articles]


def _top(stories: list[Story], n: int) -> list[Story]:
    return sorted(stories, key=lambda s: (s.score, s.created_at, _seq(s)), reverse=True)[:n]


def _facet(s: Story, cfg: dict[str, Any]) -> str | None:
    return getattr(s, _ed(cfg)["section_facet"])


def _section_stories(window: Window, cfg: dict[str, Any], name: str) -> list[Story]:
    pool = [s for s in _eligible(window, cfg) if _facet(s, cfg) == name]
    return _top(pool, cfg["limits"]["section"])


def day_stories(window: Window, day: date, cfg: dict[str, Any]) -> list[Story]:
    tz = _tz(cfg)
    pool = [s for s in _eligible(window, cfg) if s.first_published.astimezone(tz).date() == day]
    pool.sort(key=lambda s: (-s.source_count, -s.size, s.first_published))
    return pool[: cfg["limits"]["day"]]


def _today(cfg: dict[str, Any], now: datetime) -> date:
    return now.astimezone(_tz(cfg)).date()


def _front_stories(window: Window, cfg: dict[str, Any]) -> list[Story]:
    return _top(_eligible(window, cfg), cfg["limits"]["front"])


def selection(window: Window, cfg: dict[str, Any], now: datetime) -> list[str]:
    today = _today(cfg, now)
    chosen = list(_front_stories(window, cfg))
    for sec in _ed(cfg)["sections"]:
        chosen += _section_stories(window, cfg, sec["name"])
    for d in (today, today - timedelta(days=1)):
        chosen += day_stories(window, d, cfg)
    return list(dict.fromkeys(s.id for s in chosen))


def _day_key(code: str, d: date) -> str:
    return f"{code}/{d:%Y}/{d:%m}/{d:%d}.html"


def _month_key(code: str, y: int, m: int) -> str:
    return f"{code}/{y}/{m:02d}/index.html"


class _Site:
    """Everything one edition's pages share."""

    def __init__(self, window: Window, cfg: dict[str, Any], now: datetime, sources: dict[str, str]) -> None:
        self.window, self.cfg, self.now, self.sources = window, cfg, now, sources
        self.code = cfg["edition"]
        self.ed = _ed(cfg)
        self.t = self.ed["text"]
        self.tz = _tz(cfg)
        self.today = _today(cfg, now)
        self.brand = cfg["brand"]["name"]
        self.arts = window.articles
        self.css, self.js = (_assets()[e][0] for e in ("css", "js"))

    def source(self, domain: str) -> str:
        return self.sources.get(domain, domain)

    def date_text(self, d: date, kind: str = "date_long") -> str:
        wd = self.ed["weekdays"][d.weekday()]
        return self.t[kind].format(weekday=wd, day=d.day, month=self.ed["months"][d.month - 1], year=d.year)

    def when(self, dt: datetime, always_date: bool = False) -> str:
        local = dt.astimezone(self.tz)
        if local.date() == self.today and not always_date:
            return f"{local:%H:%M}"
        return f"{self.date_text(local.date(), 'date_short')}, {local:%H:%M}"

    def sources_text(self, n: int) -> str:
        return self.t["source_one" if n == 1 else "source_many"].format(n=n)

    def count_text(self, n: int) -> str:
        return self.t["count_one" if n == 1 else "count_many"].format(n=n)

    def num(self, s: Story) -> str:
        return s.id.rsplit("-", 1)[-1]

    def has_page(self, s: Story) -> bool:
        return s.source_count >= 2

    def title(self, s: Story) -> str:
        label = self.arts[s.label_url] if s.label_url else None
        return html.unescape(label.title) if label else ""

    def mark(self, s: Story) -> tuple[str, str] | None:
        if s.created_at > self.now - timedelta(hours=NEW_HOURS):
            return "new", self.t["new"]
        if s.updated_at and s.updated_at > self.now - timedelta(hours=UPDATED_HOURS):
            return "updated", self.t["updated"]
        return None

    def section_name(self, s: Story) -> str:
        return _facet(s, self.cfg) or self.ed["name"]

    def section_slug(self, name: str | None) -> str | None:
        return next((x["slug"] for x in self.ed["sections"] if x["name"] == name), None)

    def card(self, s: Story, rel: Callable[[str], str]) -> dict[str, Any]:
        label = self.arts[s.label_url]  # type: ignore[index]
        if self.has_page(s):
            href, ext = rel(f"{self.code}/story/{self.num(s)}.html"), False
        else:
            href, ext = (label.url if label.url.lower().startswith(("http://", "https://")) else "#"), True
        mark = self.mark(s)
        return {
            "title": self.title(s),
            "href": href,
            "ext": ext,
            "img": rel(s.thumb_key) if s.thumb_key else None,
            "section": self.section_name(s),
            "sources": self.sources_text(s.source_count),
            "time": self.when(s.last_published),
            "mark": mark,
        }

    def context(self, key: str, title: str, current: str = "") -> dict[str, Any]:
        """Template context shared by every page of the edition; `key` is the page's own site key."""
        start = posixpath.dirname(key) or "."

        def rel(target: str) -> str:
            return posixpath.relpath(target, start)

        def here(path: str) -> str:
            return rel(f"{self.code}/{path}")

        t = self.t
        sections = [
            {"name": x["name"], "href": here(f"s/{x['slug']}.html"), "current": current == x["slug"]}
            for x in self.ed["sections"]
        ]
        others = [
            {"code": c, "name": e["name"], "lang": e["lang"], "href": rel(f"{c}/index.html"), "current": c == self.code}
            for c, e in self.cfg["editions"].items()
        ]
        today_key = _day_key(self.code, self.today)
        return {
            "rel": rel,
            "here": here,
            "lang": self.ed["lang"],
            "brand": self.brand,
            "t": t,
            "title": f"{title} · {self.brand}" if title else self.brand,
            "css": rel(self.css),
            "js": rel(self.js),
            "home": here("index.html"),
            "sections": sections,
            "all_current": current == "front",
            "editions": others if len(others) > 1 else [],
            "feed": here("feed.xml"),
            "foot_archive": rel(today_key),
            "foot_calendar": rel(_month_key(self.code, self.today.year, self.today.month)),
            "foot_about": here("about.html"),
        }

    def render(self, template: str, key: str, ctx: dict[str, Any], cache: str) -> Page:
        body = _env().get_template(template).render(**ctx)
        return Page(key, body.encode(), HTML, cache)


def _split(cards: list[dict[str, Any]], lead: bool) -> dict[str, Any]:
    first = cards[0] if (lead and cards) else None
    rest = cards[1:] if first else cards
    return {"lead": first, "grid": rest[:GRID], "more": rest[GRID:]}


def _front(site: _Site, window: Window, cache: str) -> Page:
    key = f"{site.code}/index.html"
    ctx = site.context(key, "", "front")
    cards = [site.card(s, ctx["rel"]) for s in _front_stories(window, site.cfg)]
    ctx.update(_split(cards, True))
    ctx["top_title"] = site.t["top"]
    ctx["updated"] = site.t["updated_at"].format(time=f"{site.now.astimezone(site.tz):%H:%M}")
    ctx["today_href"] = ctx["foot_archive"]
    ctx["today_label"] = site.t["archive"]
    ctx["tagline"] = site.ed["tagline"]
    return site.render("front.html", key, ctx, cache)


def _section(site: _Site, window: Window, sec: dict[str, str], cache: str) -> Page:
    key = f"{site.code}/s/{sec['slug']}.html"
    ctx = site.context(key, sec["name"], sec["slug"])
    cards = [site.card(s, ctx["rel"]) for s in _section_stories(window, site.cfg, sec["name"])]
    ctx.update(_split(cards, False))
    ctx["heading"] = sec["name"]
    return site.render("listing.html", key, ctx, cache)


def _story(site: _Site, s: Story, cache: str) -> Page:
    key = f"{site.code}/story/{site.num(s)}.html"
    title = site.title(s)
    ctx = site.context(key, title)
    arts = sorted((site.arts[u] for u in s.members if u in site.arts), key=lambda a: (a.published_at, a.url))
    rows = [
        {
            "outlet": site.source(a.source),
            "title": html.unescape(a.title),
            "time": site.when(a.published_at),
            "url": a.url if a.url.lower().startswith(("http://", "https://")) else "#",
            "read": site.t["read_on"].format(source=site.source(a.source)),
        }
        for a in arts
    ]
    first, last = s.first_published, s.last_published
    span = site.when(first)
    if last.astimezone(site.tz) - first.astimezone(site.tz) >= timedelta(minutes=1):
        same_day = first.astimezone(site.tz).date() == last.astimezone(site.tz).date()
        span += " – " + (f"{last.astimezone(site.tz):%H:%M}" if same_day else site.when(last, True))
    first_art = arts[0] if arts else None
    day = first.astimezone(site.tz).date()
    img = ctx["rel"](s.thumb_key) if s.thumb_key else None
    credit = site.t["photo"].format(source=site.source(s.thumb_source)) if (img and s.thumb_source) else None
    facet = _facet(s, site.cfg)
    slug = site.section_slug(facet)
    ctx.update(
        {
            "heading": title,
            "img": img,
            "credit": credit,
            "section": site.section_name(s),
            "section_href": ctx["here"](f"s/{slug}.html") if slug else None,
            "sources": site.sources_text(s.source_count),
            "span": span,
            "mark": site.mark(s),
            "first_by": (
                site.t["first_by"].format(source=site.source(first_art.source), time=site.when(first_art.published_at))
                if first_art
                else None
            ),
            "rows": rows,
            "day_href": ctx["rel"](_day_key(site.code, day)),
            "day_label": site.t["story_day"].format(date=site.date_text(day)),
        }
    )
    return site.render("story.html", key, ctx, cache)


def _index_map(days: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    return {date.fromisoformat(d["date"]): d for d in days if d.get("stories")}


def _live_days(site: _Site, window: Window, days: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    """The days index with today and yesterday recomputed from the window."""
    index = _index_map(days)
    for d in (site.today, site.today - timedelta(days=1)):
        stories = day_stories(window, d, site.cfg)
        if stories:
            index[d] = {"date": d.isoformat(), "stories": len(stories), "lead_title": site.title(stories[0])}
        else:
            index.pop(d, None)
    return index


def _day(site: _Site, window: Window, d: date, index: dict[date, dict[str, Any]], cache: str) -> Page:
    key = _day_key(site.code, d)
    heading = site.t["day_title"].format(date=site.date_text(d))
    ctx = site.context(key, heading)
    rel = ctx["rel"]
    cards = [site.card(s, rel) for s in day_stories(window, d, site.cfg)]
    ctx.update(_split(cards, False))
    known = sorted(set(index) | {site.today, site.today - timedelta(days=1)})
    prev = max((x for x in known if x < d), default=None)
    nxt = min((x for x in known if x > d), default=None)
    ctx.update(
        {
            "heading": heading,
            "is_day": True,
            "prev": {"href": rel(_day_key(site.code, prev)), "label": site.t["prev_day"]} if prev else None,
            "next": {"href": rel(_day_key(site.code, nxt)), "label": site.t["next_day"]} if nxt else None,
            "cal_href": rel(_month_key(site.code, d.year, d.month)),
            "cal_label": f"{site.t['calendar']}: {site.date_text(d, 'month_year')}",
            "empty": site.t["no_stories"] if not cards else None,
        }
    )
    return site.render("listing.html", key, ctx, cache)


def _month(site: _Site, y: int, m: int, index: dict[date, dict[str, Any]], cache: str) -> Page:
    key = _month_key(site.code, y, m)
    first = date(y, m, 1)
    heading = site.date_text(first, "month_year")
    ctx = site.context(key, f"{site.t['calendar']}: {heading}")
    rel = ctx["rel"]
    cells = []
    for n in range(1, calendar.monthrange(y, m)[1] + 1):
        d = date(y, m, n)
        e = index.get(d)
        cells.append(
            {
                "day": n,
                "weekday": site.ed["weekdays"][d.weekday()],
                "href": rel(_day_key(site.code, d)) if e else None,
                "count": site.count_text(e["stories"]) if e else None,
                "lead": html.unescape(e.get("lead_title") or "") if e else None,
                "today": d == site.today,
            }
        )
    months = {(d.year, d.month) for d in index} | {(site.today.year, site.today.month)}
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    ctx.update(
        {
            "heading": heading,
            "cells": cells,
            "offset": first.weekday(),
            "weekdays": site.ed["weekdays"],
            "prev": (
                {"href": rel(_month_key(site.code, py, pm)), "label": site.t["prev_month"]}
                if (py, pm) in months
                else None
            ),
            "next": (
                {"href": rel(_month_key(site.code, ny, nm)), "label": site.t["next_month"]}
                if (ny, nm) in months and (ny, nm) <= (site.today.year, site.today.month)
                else None
            ),
            "calendar_title": site.t["calendar"],
        }
    )
    return site.render("calendar.html", key, ctx, cache)


def _about(site: _Site, window: Window, cache: str) -> Page:
    key = f"{site.code}/about.html"
    ctx = site.context(key, site.t["about"])
    domains = {a.source for a in window.articles.values()} | set(window.source_last_ok)
    outlets = sorted(
        ({"name": site.source(d), "domain": d} for d in domains if d in site.sources), key=lambda o: o["name"].lower()
    )
    paras = site.t["about_body"].format(brand=site.brand).strip().splitlines()
    ctx.update(
        {
            "heading": site.t["about"],
            "paras": paras,
            "contact": site.t["contact"].format(email=cfg_email(site.cfg)),
            "outlets": outlets,
            "outlets_title": site.t["about_sources"],
        }
    )
    return site.render("about.html", key, ctx, cache)


def cfg_email(cfg: dict[str, Any]) -> str:
    return cfg["brand"].get("contact_email", "")


def _feed(site: _Site, window: Window, cache: str) -> Page:
    key = f"{site.code}/feed.xml"
    base = (site.cfg.get("base_url") or "").rstrip("/")

    def url(path: str) -> str:
        return f"{base}/{site.code}/{path}" if base else path

    items = []
    for s in _front_stories(window, site.cfg)[: site.cfg["limits"]["feed"]]:
        label = site.arts[s.label_url]  # type: ignore[index]
        link = url(f"story/{site.num(s)}.html") if site.has_page(s) else label.url
        items.append(
            "<item>"
            f"<title>{escape(site.title(s))}</title><link>{escape(link)}</link>"
            f'<guid isPermaLink="false">{escape(s.id)}</guid>'
            f"<pubDate>{format_datetime(s.first_published.astimezone(ZoneInfo('UTC')))}</pubDate>"
            f"<description>{escape(site.sources_text(s.source_count))}</description></item>"
        )
    head = f"{site.brand} · {site.ed['name']}"
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>{escape(head)}</title><link>{escape(url('index.html'))}</link>"
        f"<description>{escape(site.ed['tagline'])}</description><language>{site.ed['lang']}</language>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    return Page(key, body.encode(), "application/rss+xml; charset=utf-8", cache)


def sitemap_paths(
    window: Window, cfg: dict[str, Any], now: datetime, days: list[dict[str, Any]], story_ids: list[str] | None = None
) -> list[str]:
    """Site keys of an edition for the sitemap: front, sections, about, last 30 day pages, story pages."""
    code = cfg["edition"]
    paths = [f"{code}/index.html", f"{code}/about.html"]
    paths += [f"{code}/s/{x['slug']}.html" for x in _ed(cfg)["sections"]]
    paths += [_day_key(code, date.fromisoformat(d["date"])) for d in days[:30] if d.get("stories")]
    ids = selection(window, cfg, now) if story_ids is None else story_ids
    paths += [f"{code}/story/{i.rsplit('-', 1)[-1]}.html" for i in ids if i in window.stories]
    return list(dict.fromkeys(paths))


def render_edition(
    window: Window,
    cfg: dict[str, Any],
    now: datetime,
    days: list[dict[str, Any]],
    sources: dict[str, str],
    touched: set[str] | list[str],
) -> list[Page]:
    cfg = {**cfg, "edition": cfg.get("edition") or window.edition}
    site = _Site(window, cfg, now, sources)
    html_cache = f"public, max-age={cfg['cache_seconds']['html']}"
    pages = [_front(site, window, html_cache)]
    pages += [_section(site, window, sec, html_cache) for sec in site.ed["sections"]]

    shown = set(selection(window, cfg, now)) | set(touched)
    for sid in sorted(shown):
        s = window.stories.get(sid)
        if s and site.has_page(s) and s.label_url in window.articles:
            pages.append(_story(site, s, html_cache))

    index = _live_days(site, window, days)
    for d in (site.today, site.today - timedelta(days=1)):
        pages.append(_day(site, window, d, index, html_cache))
    months = [(site.today.year, site.today.month)]
    if site.today.day <= 2:
        months.append((site.today.year, site.today.month - 1) if site.today.month > 1 else (site.today.year - 1, 12))
    pages += [_month(site, y, m, index, html_cache) for y, m in months]
    pages.append(_about(site, window, html_cache))
    pages.append(_feed(site, window, html_cache))
    return pages


def render_root(cfg: dict[str, Any], summaries: list[dict[str, Any]], now: datetime) -> list[Page]:
    order = list(cfg["editions"])
    have = {s["edition"]: s for s in summaries}
    codes = [c for c in order if c in have] or order
    first = cfg["editions"][codes[0]]
    editions = [
        {
            "name": cfg["editions"][c]["name"],
            "lang": cfg["editions"][c]["lang"],
            "tagline": cfg["editions"][c]["tagline"],
            "href": f"{c}/index.html",
        }
        for c in codes
    ]
    css, js = (_assets()[e][0] for e in ("css", "js"))
    ctx = {
        "lang": first["lang"],
        "brand": cfg["brand"]["name"],
        "title": cfg["brand"]["name"],
        "t": first["text"],
        "css": css,
        "js": js,
        "editions": [],
        "sections": [],
        "home": "index.html",
        "chooser": editions,
    }
    cache = f"public, max-age={cfg['cache_seconds']['html']}"
    body = _env().get_template("chooser.html").render(**ctx)
    base = (cfg.get("base_url") or "").rstrip("/")
    robots = "User-agent: *\nDisallow: /lab/\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else "")
    pages = [
        Page("index.html", body.encode(), HTML, cache),
        Page("robots.txt", robots.encode(), "text/plain; charset=utf-8", cache),
    ]
    if base:
        paths = ["index.html"]
        for c in codes:
            paths += have[c].get("urls") or [f"{c}/index.html", f"{c}/about.html"]
        locs = "".join(f"<url><loc>{escape(base + '/' + p)}</loc></url>" for p in dict.fromkeys(paths))
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{locs}</urlset>\n"
        )
        pages.append(Page("sitemap.xml", xml.encode(), "application/xml; charset=utf-8", cache))
    return pages
