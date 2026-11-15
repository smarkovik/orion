"""Public site pages: pure functions of the window and the site settings."""

import calendar
import hashlib
import html
import io
import json
import posixpath
import re
from datetime import date, datetime, time, timedelta
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
DEVELOPING_HOURS = 2
BRIEFING_FROM = time(18, 0)
BRIEFING_AT = time(8, 0)
BRIEFING_ENTRY_UNTIL = 12
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


def _colors(cfg: dict[str, Any] | None) -> dict[str, str]:
    base = {"accent": "#0a58ad", "background": "#f6f5f2", "theme_light": "#ffffff", "theme_dark": "#1e2024"}
    return {**base, **((cfg or {}).get("colors") or {})}


def _slug(brand: str) -> str:
    return re.sub(r"\W+", "-", brand.lower()).strip("-") or "site"


def _font(px: int) -> tuple[Any, int]:
    """A bold font if one is installed, else Pillow's built-in one with a faux-bold stroke."""
    from PIL import ImageFont

    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "Roboto-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px), 0
        except OSError:
            continue
    try:
        return ImageFont.load_default(px), max(1, px // 22)
    except TypeError:
        return ImageFont.load_default(), 0


def _icon_png(letter: str, size: int, accent: str, rounded: bool, letter_size: float) -> bytes:
    from PIL import Image, ImageDraw

    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (0, 0, big - 1, big - 1)
    d.rounded_rectangle(box, radius=big * 0.22, fill=accent) if rounded else d.rectangle(box, fill=accent)
    font, stroke = _font(int(big * letter_size))
    x0, y0, x1, y1 = d.textbbox((0, 0), letter, font=font, stroke_width=stroke)
    at = ((big - (x1 - x0)) / 2 - x0, (big - (y1 - y0)) / 2 - y0)
    d.text(at, letter, font=font, fill="#ffffff", stroke_width=stroke, stroke_fill="#ffffff")
    out = io.BytesIO()
    img.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


@lru_cache(maxsize=4)
def _icons(brand: str, accent: str) -> dict[str, tuple[str, bytes]]:
    """Brand icons by role: (site key, PNG). Empty when Pillow is missing."""
    try:
        specs = {
            "icon-192": (192, True, 0.62),
            "icon-512": (512, True, 0.62),
            "icon-maskable-512": (512, False, 0.5),
            "apple-touch-icon": (180, False, 0.58),
        }
        out = {}
        for name, (size, rounded, frac) in specs.items():
            body = _icon_png(brand[:1].upper() or "S", size, accent, rounded, frac)
            out[name] = (f"assets/{name}.{hashlib.sha1(body).hexdigest()[:10]}.png", body)
        return out
    except Exception:  # noqa: BLE001 - icons are optional
        return {}


def _sw_page(brand: str) -> Page:
    a = _assets()
    src = (HERE / "static" / "sw.js").read_text(encoding="utf-8")
    version = hashlib.sha1((src + a["css"][0] + a["js"][0]).encode()).hexdigest()[:10]
    body = src.replace("__PREFIX__", _slug(brand)).replace("__VERSION__", version)
    return Page("sw.js", body.encode(), "text/javascript; charset=utf-8", "no-cache")


def render_assets(cfg: dict[str, Any] | None = None) -> tuple[list[Page], str, str]:
    a = _assets()
    brand = ((cfg or {}).get("brand") or {}).get("name") or "Site"
    pages = [Page(key, body, ctype, ASSET_CACHE) for key, body, ctype in (a["css"], a["js"])]
    pages += [Page(key, body, "image/png", ASSET_CACHE) for key, body in _icons(brand, _colors(cfg)["accent"]).values()]
    pages.append(_sw_page(brand))
    return pages, a["css"][0], a["js"][0]


def _ed(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["editions"][cfg["edition"]]


def _tz(cfg: dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(_ed(cfg)["timezone"])


def _seq(s: Story) -> int:
    tail = s.id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _num(s: Story) -> str:
    return s.id.rsplit("-", 1)[-1]


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


def day_stories(window: Window, day: date, cfg: dict[str, Any], limit: bool = True) -> list[Story]:
    tz = _tz(cfg)
    pool = [s for s in _eligible(window, cfg) if s.first_published.astimezone(tz).date() == day]
    pool.sort(key=lambda s: (-s.source_count, -s.size, s.first_published))
    return pool[: cfg["limits"]["day"]] if limit else pool


def _today(cfg: dict[str, Any], now: datetime) -> date:
    return now.astimezone(_tz(cfg)).date()


def _front_stories(window: Window, cfg: dict[str, Any]) -> list[Story]:
    return _top(_eligible(window, cfg), cfg["limits"]["front"])


def live_dates(
    window: Window, cfg: dict[str, Any], now: datetime, days: list[dict[str, Any]] | None = None
) -> list[date]:
    """Today, yesterday, and older days still in the window unless the index already holds a fuller version."""
    today = _today(cfg, now)
    tz = _tz(cfg)
    known = {date.fromisoformat(d["date"]): d.get("stories", 0) for d in days or []}
    out = {today, today - timedelta(days=1)}
    for d in {s.first_published.astimezone(tz).date() for s in _eligible(window, cfg)}:
        if d < today - timedelta(days=1) and len(day_stories(window, d, cfg, limit=False)) >= known.get(d, 0):
            out.add(d)
    return sorted(out)


def story_summary(window: Window, s: Story, cfg: dict[str, Any]) -> dict[str, Any]:
    """What a week page needs from a story, kept in days.json so it survives the story leaving the window."""
    label = window.articles.get(s.label_url or "")
    paged = s.source_count >= 2
    url = label.url if label and label.url.lower().startswith(("http://", "https://")) else None
    return {
        "id": s.id,
        "title": html.unescape(label.title) if label else "",
        "thumb": s.thumb_key or "",
        "sources": s.source_count,
        "size": s.size,
        "first_published": s.first_published.isoformat(),
        "page": f"{cfg['edition']}/story/{_num(s)}.html" if paged else None,
        "url": None if paged else url,
        "section": _facet(s, cfg) or _ed(cfg)["name"],
    }


def briefing_stories(window: Window, cfg: dict[str, Any], day: date) -> list[Story]:
    """Stories with an article published between 18:00 the evening before and 08:00 of `day` (local)."""
    tz = _tz(cfg)
    start = datetime.combine(day - timedelta(days=1), BRIEFING_FROM, tz)
    end = datetime.combine(day, BRIEFING_AT, tz)
    pool = [
        s
        for s in _eligible(window, cfg)
        if any(u in window.articles and start <= window.articles[u].published_at < end for u in s.members)
    ]
    pool.sort(key=lambda s: (-s.source_count, -s.size, s.first_published))
    return pool[: cfg["limits"].get("briefing", 10)]


def _briefing_key(code: str, d: date) -> str:
    return f"{code}/briefing/{d.isoformat()}.html"


def _briefing_due(cfg: dict[str, Any], now: datetime, days: list[dict[str, Any]] | None) -> bool:
    """Today's briefing is built by the first build at or after 08:00 local, once."""
    local = now.astimezone(_tz(cfg))
    if local.time() < BRIEFING_AT:
        return False
    today = local.date().isoformat()
    return not any(d["date"] == today and d.get("briefing") for d in days or [])


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _week_key(code: str, monday: date) -> str:
    year, week, _ = monday.isocalendar()
    return f"{code}/week/{year}-W{week:02d}.html"


def _week_tops(
    window: Window, cfg: dict[str, Any], now: datetime, days: list[dict[str, Any]] | None
) -> tuple[dict[date, list[dict[str, Any]]], list[date]]:
    """Top lists per day (stored, with live days recomputed from the window) and the Mondays of weeks to render."""
    today = _today(cfg, now)
    n = cfg["limits"].get("week", 10)
    stored = {date.fromisoformat(d["date"]): d for d in days or []}
    tops = {d: e["top"] for d, e in stored.items() if e.get("top")}
    live = live_dates(window, cfg, now, days)
    for d in live:
        pool = day_stories(window, d, cfg, limit=False)
        old = stored.get(d)
        if d != today and old and old.get("top") and old.get("stories", 0) > len(pool):
            continue
        if pool:
            tops[d] = [story_summary(window, s, cfg) for s in pool[:n]]
        else:
            tops.pop(d, None)
    this = _monday(today)
    last = this - timedelta(days=7)
    render = [this]
    if today.weekday() <= 1 or any(_monday(d) == last for d in live):
        render.insert(0, last)
    return tops, render


def _week_list(tops: dict[date, list[dict[str, Any]]], monday: date, n: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for i in range(7):
        for item in tops.get(monday + timedelta(days=i), []):
            merged[item["id"]] = item
    ranked = sorted(
        merged.values(), key=lambda x: (-x["sources"], -x["size"], datetime.fromisoformat(x["first_published"]))
    )
    return ranked[:n]


def selection(
    window: Window, cfg: dict[str, Any], now: datetime, days: list[dict[str, Any]] | None = None
) -> list[str]:
    chosen = list(_front_stories(window, cfg))
    for sec in _ed(cfg)["sections"]:
        chosen += _section_stories(window, cfg, sec["name"])
    for d in live_dates(window, cfg, now, days):
        chosen += day_stories(window, d, cfg)
    ids = [s.id for s in chosen]
    if _briefing_due(cfg, now, days):
        ids += [s.id for s in briefing_stories(window, cfg, _today(cfg, now))]
    tops, weeks = _week_tops(window, cfg, now, days)
    for monday in weeks:
        ids += [x["id"] for x in _week_list(tops, monday, cfg["limits"].get("week", 10)) if x["id"] in window.stories]
    return list(dict.fromkeys(ids))


def _day_key(code: str, d: date) -> str:
    return f"{code}/{d:%Y}/{d:%m}/{d:%d}.html"


def _month_key(code: str, y: int, m: int) -> str:
    return f"{code}/{y}/{m:02d}/index.html"


class _Site:
    """Everything one edition's pages share."""

    def __init__(
        self,
        window: Window,
        cfg: dict[str, Any],
        now: datetime,
        sources: dict[str, str],
        logos: dict[str, str | None] | None = None,
    ) -> None:
        self.window, self.cfg, self.now, self.sources = window, cfg, now, sources
        self.logos = logos or {}
        self.briefings: set[date] = set()
        self.code = cfg["edition"]
        self.ed = _ed(cfg)
        self.t = self.ed["text"]
        self.tz = _tz(cfg)
        self.today = _today(cfg, now)
        self.brand = cfg["brand"]["name"]
        self.arts = window.articles
        self.css, self.js = (_assets()[e][0] for e in ("css", "js"))
        self.colors = _colors(cfg)
        self.icons = _icons(self.brand, self.colors["accent"])

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
        return _num(s)

    def has_page(self, s: Story) -> bool:
        return s.source_count >= 2

    def title(self, s: Story) -> str:
        label = self.arts[s.label_url] if s.label_url else None
        return html.unescape(label.title) if label else ""

    def chip(self, domain: str, rel: Callable[[str], str]) -> dict[str, Any]:
        name = self.source(domain)
        key = self.logos.get(domain)
        return {
            "logo": rel(key) if key else None,
            "initial": next((c for c in name if c.isalnum()), "?").upper(),
            "name": name,
        }

    def mark(self, s: Story) -> tuple[str, str] | None:
        fresh = self.now - timedelta(hours=DEVELOPING_HOURS)
        recent = sum(1 for u in s.members if u in self.arts and self.arts[u].published_at >= fresh)
        if recent >= 2 and s.source_count >= self.cfg["limits"]["min_sources"]:
            return "developing", self.t["developing"]
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
        arts = sorted((self.arts[u] for u in s.members if u in self.arts), key=lambda a: a.published_at)
        doms = list(dict.fromkeys(a.source for a in arts))
        return {
            "title": self.title(s),
            "href": href,
            "ext": ext,
            "img": rel(s.thumb_key) if s.thumb_key else None,
            "section": self.section_name(s),
            "sources": self.sources_text(s.source_count),
            "time": self.when(s.last_published),
            "mark": mark,
            "created": s.created_at.isoformat(),
            "chips": [self.chip(d, rel) for d in doms[:3]],
            "more": max(0, len(doms) - 3),
        }

    def summary_card(self, x: dict[str, Any], rel: Callable[[str], str]) -> dict[str, Any]:
        href, ext = (rel(x["page"]), False) if x.get("page") else (x.get("url") or "#", True)
        return {
            "title": x["title"],
            "href": href,
            "ext": ext,
            "img": rel(x["thumb"]) if x.get("thumb") else None,
            "section": x["section"],
            "sources": self.sources_text(x["sources"]),
            "time": self.when(datetime.fromisoformat(x["first_published"])),
            "mark": None,
            "created": None,
            "chips": [],
            "more": 0,
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
        icon = self.icons.get("apple-touch-icon")
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
            "foot_week": rel(_week_key(self.code, _monday(self.today))),
            "manifest": here("manifest.webmanifest"),
            "touch_icon": rel(icon[0]) if icon else None,
            "theme_light": self.colors["theme_light"],
            "theme_dark": self.colors["theme_dark"],
            "sw": rel("sw.js"),
            "visit": f"{_slug(self.brand)}:visit:{self.code}",
            "follow": f"{_slug(self.brand)}:follow:{self.code}",
            "follow_json": here("follow.json"),
            "foot_briefing": rel(_briefing_key(self.code, max(self.briefings))) if self.briefings else None,
            "briefing_href": None,
            "share_targets": self.cfg.get("share_targets") or [],
        }

    def render(self, template: str, key: str, ctx: dict[str, Any], cache: str) -> Page:
        body = _env().get_template(template).render(**ctx)
        return Page(key, body.encode(), HTML, cache)


def _split(cards: list[dict[str, Any]], lead: bool) -> dict[str, Any]:
    first = cards[0] if (lead and cards) else None
    rest = cards[1:] if first else cards
    return {"lead": first, "grid": rest[:GRID], "more": rest[GRID:]}


def _front(site: _Site, window: Window, cache: str, last_week: bool) -> Page:
    key = f"{site.code}/index.html"
    ctx = site.context(key, "", "front")
    ctx["week_href"] = ctx["foot_week"]
    if site.today in site.briefings and site.now.astimezone(site.tz).hour < BRIEFING_ENTRY_UNTIL:
        ctx["briefing_href"] = ctx["rel"](_briefing_key(site.code, site.today))
    ctx["last_week_href"] = (
        ctx["rel"](_week_key(site.code, _monday(site.today) - timedelta(days=7))) if last_week else None
    )
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


def _og(site: _Site, key: str, title: str, s: Story) -> dict[str, str]:
    lang = site.ed["lang"]
    og = {"title": title, "type": "article", "site_name": site.brand, "locale": f"{lang}_{lang.upper()}"}
    base = (site.cfg.get("base_url") or "").rstrip("/")
    if base:
        og["url"] = f"{base}/{key}"
        if s.thumb_key:
            og["image"] = f"{base}/{s.thumb_key}"
    return og


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
            "chip": site.chip(a.source, ctx["rel"]),
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
            "share_title": title,
            "story_id": s.id,
            "size": s.size,
            "og": _og(site, key, title, s),
        }
    )
    return site.render("story.html", key, ctx, cache)


def _week_range(site: _Site, monday: date) -> str:
    sunday = monday + timedelta(days=6)
    start = site.date_text(monday, "date_short") + (f" {monday.year}" if monday.year != sunday.year else "")
    return f"{start} – {site.date_text(sunday, 'date_short')} {sunday.year}"


def _week(
    site: _Site,
    monday: date,
    tops: dict[date, list[dict[str, Any]]],
    weeks: list[date],
    index: dict[date, dict[str, Any]],
    cache: str,
) -> Page:
    key = _week_key(site.code, monday)
    items = _week_list(tops, monday, site.cfg["limits"].get("week", 10))
    heading = site.t["week_title"].format(n=len(items)) if items else site.t["this_week"]
    ctx = site.context(key, heading)
    rel = ctx["rel"]
    cards = [site.summary_card(x, rel) for x in items]
    ctx.update(_split(cards, True))
    this = _monday(site.today)
    before = max((w for w in weeks if w < monday), default=None)
    after = min((w for w in weeks if monday < w <= this), default=None)
    day_cells = []
    for i in range(7):
        d = monday + timedelta(days=i)
        e = index.get(d)
        if e and d <= site.today:
            day_cells.append(
                {
                    "href": rel(_day_key(site.code, d)),
                    "weekday": site.ed["weekdays"][d.weekday()],
                    "date": site.date_text(d, "date_short"),
                    "count": site.count_text(e["stories"]),
                }
            )
    ctx.update(
        {
            "heading": heading,
            "range": _week_range(site, monday),
            "prev": {"href": rel(_week_key(site.code, before)), "label": site.t["prev_week"]} if before else None,
            "next": {"href": rel(_week_key(site.code, after)), "label": site.t["next_week"]} if after else None,
            "day_cells": day_cells,
            "share_title": heading,
            "empty": site.t["no_stories"] if not cards else None,
        }
    )
    return site.render("week.html", key, ctx, cache)


def _briefing(site: _Site, stories: list[Story], cache: str) -> Page:
    key = _briefing_key(site.code, site.today)
    heading = site.t["briefing"]
    ctx = site.context(key, heading)
    rel = ctx["rel"]
    cards = [{**site.card(s, rel), "mark": None} for s in stories]
    ctx.update(_split(cards, True))
    ctx.update(
        {
            "heading": heading,
            "sub": site.t["briefing_sub"],
            "date_label": site.date_text(site.today),
            "share_title": heading,
            "day_href": rel(_day_key(site.code, site.today)),
            "day_label": site.t["story_day"].format(date=site.date_text(site.today)),
            "empty": None,
        }
    )
    return site.render("briefing.html", key, ctx, cache)


def _follow(site: _Site, window: Window, cache: str) -> Page:
    stories = {
        s.id: [s.size, s.last_activity_at.isoformat(), site.title(s), f"story/{site.num(s)}.html"]
        for s in window.stories.values()
        if site.has_page(s) and s.label_url in window.articles
    }
    doc = {"generated": site.now.isoformat(), "stories": stories}
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
    return Page(f"{site.code}/follow.json", body, "application/json; charset=utf-8", cache)


def _manifest(site: _Site, cache: str) -> Page:
    key = f"{site.code}/manifest.webmanifest"
    doc: dict[str, Any] = {
        "name": f"{site.brand} · {site.ed['name']}",
        "short_name": site.brand,
        "description": site.ed["tagline"],
        "start_url": "index.html",
        "scope": "./",
        "display": "standalone",
        "lang": site.ed["lang"],
        "background_color": site.colors["background"],
        "theme_color": site.colors["theme_light"],
    }
    icons = []
    for name, size, purpose in (
        ("icon-192", 192, "any"),
        ("icon-512", 512, "any"),
        ("icon-maskable-512", 512, "maskable"),
    ):
        if name in site.icons:
            icons.append(
                {
                    "src": posixpath.relpath(site.icons[name][0], site.code),
                    "sizes": f"{size}x{size}",
                    "type": "image/png",
                    "purpose": purpose,
                }
            )
    if icons:
        doc["icons"] = icons
    return Page(key, json.dumps(doc, ensure_ascii=False, indent=1).encode(), "application/manifest+json", cache)


def _index_map(days: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    return {date.fromisoformat(d["date"]): d for d in days if d.get("stories")}


def _live_days(site: _Site, window: Window, days: list[dict[str, Any]], live: list[date]) -> dict[date, dict[str, Any]]:
    """The days index with the live days recomputed from the window."""
    index = _index_map(days)
    for d in live:
        stories = day_stories(window, d, site.cfg)
        if stories:
            total = len(day_stories(window, d, site.cfg, limit=False))
            index[d] = {"date": d.isoformat(), "stories": total, "lead_title": site.title(stories[0])}
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
            "briefing_href": rel(_briefing_key(site.code, d)) if d in site.briefings else None,
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
        ({"name": site.source(d), "domain": d, "chip": site.chip(d, ctx["rel"])} for d in domains if d in site.sources),
        key=lambda o: o["name"].lower(),
    )
    paras = site.t["about_body"].format(brand=site.brand).strip().splitlines()
    ctx.update(
        {
            "heading": site.t["about"],
            "paras": paras,
            "contact": site.t["contact"].format(email=cfg_email(site.cfg)),
            "outlets": outlets,
            "outlets_title": site.t["about_sources"],
            "install_tip": site.t["install_tip"].format(brand=site.brand),
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
    paths.append(_week_key(code, _monday(_today(cfg, now))))
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
    logos: dict[str, str | None] | None = None,
) -> list[Page]:
    cfg = {**cfg, "edition": cfg.get("edition") or window.edition}
    site = _Site(window, cfg, now, sources, logos)
    html_cache = f"public, max-age={cfg['cache_seconds']['html']}"
    site.briefings = {date.fromisoformat(d["date"]) for d in days if d.get("briefing")}
    brief_stories: list[Story] = []
    if _briefing_due(cfg, now, days):
        brief_stories = briefing_stories(window, cfg, site.today)
    if brief_stories:
        site.briefings.add(site.today)
        today_entry = next((d for d in days if d["date"] == site.today.isoformat()), None)
        if today_entry is None:
            days.insert(0, {"date": site.today.isoformat(), "stories": 0, "lead_title": "", "lead_story": ""})
            today_entry = days[0]
        today_entry["briefing"] = True  # the caller saves the index: the flag keeps the briefing frozen
    tops, render_weeks = _week_tops(window, cfg, now, days)
    data_weeks = sorted({_monday(d) for d, v in tops.items() if v})
    last = _monday(site.today) - timedelta(days=7)
    pages = [_front(site, window, html_cache, last in data_weeks)]
    pages += [_section(site, window, sec, html_cache) for sec in site.ed["sections"]]

    shown = set(selection(window, cfg, now)) | set(touched)
    for sid in sorted(shown):
        s = window.stories.get(sid)
        if s and site.has_page(s) and s.label_url in window.articles:
            pages.append(_story(site, s, html_cache))

    live = live_dates(window, cfg, now, days)
    index = _live_days(site, window, days, live)
    for d in live:
        pages.append(_day(site, window, d, index, html_cache))
    months = [(site.today.year, site.today.month)]
    if site.today.day <= 2:
        months.append((site.today.year, site.today.month - 1) if site.today.month > 1 else (site.today.year - 1, 12))
    pages += [_month(site, y, m, index, html_cache) for y, m in months]
    weeks = sorted(set(data_weeks) | {_monday(site.today)})
    pages += [_week(site, m, tops, weeks, index, html_cache) for m in render_weeks]
    pages.append(_manifest(site, html_cache))
    pages.append(_follow(site, window, html_cache))
    if brief_stories:
        pages.append(_briefing(site, brief_stories, html_cache))
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
    colors = _colors(cfg)
    icon = _icons(cfg["brand"]["name"], colors["accent"]).get("apple-touch-icon")
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
        "touch_icon": icon[0] if icon else None,
        "theme_light": colors["theme_light"],
        "theme_dark": colors["theme_dark"],
        "sw": "sw.js",
    }
    cache = f"public, max-age={cfg['cache_seconds']['html']}"
    body = _env().get_template("chooser.html").render(**ctx)
    base = (cfg.get("base_url") or "").rstrip("/")
    robots = "User-agent: *\nDisallow: /lab/\nDisallow: /system/\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else "")
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
