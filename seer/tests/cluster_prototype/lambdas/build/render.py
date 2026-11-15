"""Static site pages from the in-memory window (same templates as the old Postgres export)."""

import gzip
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import yaml
from jinja2 import Environment, FileSystemLoader

from model import Article, Story, Window
from seer_common import store

TZ = ZoneInfo("Europe/Skopje")
EDITIONS = {"mk": "Македонија", "fr": "France"}
NONE = "none"
TEMPLATES = Path(os.environ.get("TEMPLATES_DIR", "/var/task/templates"))
SOURCES_FILE = os.environ.get("SOURCES_FILE", "/var/task/sources.yaml")
CACHE_SECONDS = int(os.environ.get("SITE_CACHE_SECONDS", "300"))
LIMITS = {"top": int(os.environ.get("TOP_LIMIT", "60")), "latest": int(os.environ.get("LATEST_LIMIT", "60"))}
PAGES = {"top": "index.html", "latest": "latest.html"}
MIN_SOURCES = int(os.environ.get("MIN_SOURCES", "2"))


def local_dt(value: datetime | None) -> str:
    return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if value else "?"


def safe_url(value: str) -> str:
    return value if value.lower().startswith(("http://", "https://")) else "#"


def edition_name(code: str) -> str:
    return EDITIONS.get(code, code)


_env: Environment | None = None
_sources: dict[str, Any] | None = None


def env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
        _env.filters["local_dt"] = local_dt
        _env.filters["safe_url"] = safe_url
        _env.filters["edition_name"] = edition_name
    return _env


def sources_cfg() -> dict[str, Any]:
    global _sources
    if _sources is None:
        try:
            with open(SOURCES_FILE, encoding="utf-8") as f:
                _sources = yaml.safe_load(f) or {}
        except OSError:
            _sources = {}
    return _sources


def source_names() -> dict[str, str]:
    eds = sources_cfg().get("editions") or {}
    return {s["domain"]: s.get("name", s["domain"]) for e in eds.values() for s in e.get("sources") or []}


def known_editions() -> list[str]:
    return list((sources_cfg().get("editions") or {}).keys()) or list(EDITIONS)


def all_editions(current: str) -> list[str]:
    known = known_editions()
    return [*known, current] if current not in known else known


def _seq(story: Story) -> int:
    tail = story.id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _facets(stories: list[Story], attr: str) -> list[dict[str, Any]]:
    counts = Counter(getattr(s, attr) or NONE for s in stories)
    return [{"value": v, "n": n} for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _story_dict(s: Story, arts: dict[str, Article], now: datetime) -> dict[str, Any]:
    label = arts[s.label_url] if s.label_url else None
    return {
        "id": s.id,
        "size": s.size,
        "source_count": s.source_count,
        "first_published": s.first_published,
        "last_published": s.last_published,
        "score": s.score,
        "region": s.region,
        "region_votes": s.region_votes,
        "subject": s.subject,
        "subject_votes": s.subject_votes,
        "label_title": label.title if label else "",
        "label_url": label.url if label else "#",
        "image_url": label.image_url if label else None,
        "is_new": s.created_at > now - timedelta(hours=3),
        "is_updated": bool(s.updated_at and s.updated_at > now - timedelta(hours=6)),
    }


def _members(s: Story, arts: dict[str, Article], names: dict[str, str], now: datetime) -> list[dict[str, Any]]:
    members = [arts[u] for u in s.members if u in arts]
    vecs = [a.vector for a in members if a.vector is not None]
    centroid = np.mean(vecs, axis=0) if vecs else None
    if centroid is not None:
        centroid = centroid / np.linalg.norm(centroid)
    rows = []
    for a in members:
        sim = float(a.vector @ centroid) if centroid is not None and a.vector is not None else 0.0
        rows.append(
            {
                "similarity": sim,
                "title": a.title,
                "url": a.url,
                "published_at": a.published_at,
                "source_categories": a.source_categories,
                "changed": bool(a.content_changed_at and a.content_changed_at > now - timedelta(hours=6)),
                "source_name": names.get(a.source, a.source),
            }
        )
    rows.sort(key=lambda r: (-r["similarity"], r["url"]))
    return rows


def _visible(window: Window) -> list[Story]:
    return [s for s in window.stories.values() if s.source_count >= MIN_SOURCES and s.label_url in window.articles]


def render_edition(window: Window, now: datetime) -> dict[str, str]:
    visible = _visible(window)
    regions, subjects = _facets(visible, "region"), _facets(visible, "subject")
    names = source_names()
    editions = all_editions(window.edition)
    orders = {
        "top": sorted(visible, key=lambda s: (s.score, s.created_at, _seq(s)), reverse=True),
        "latest": sorted(visible, key=lambda s: (s.created_at, _seq(s)), reverse=True),
    }
    pages: dict[str, str] = {}
    for view, name in PAGES.items():
        chosen = orders[view][: LIMITS[view]]
        html = (
            env()
            .get_template("static_page.html")
            .render(
                edition=window.edition,
                editions=editions,
                view=view,
                views=list(PAGES),
                pages=PAGES,
                stories=[_story_dict(s, window.articles, now) for s in chosen],
                members={s.id: _members(s, window.articles, names, now) for s in chosen},
                regions=regions,
                subjects=subjects,
                total=len(visible),
                min_sources=MIN_SOURCES,
                none_value=NONE,
                generated_at=local_dt(now),
            )
        )
        pages[f"{window.edition}/{name}"] = html
    return pages


def edition_summary(window: Window, now: datetime) -> dict[str, Any]:
    return {
        "edition": window.edition,
        "name": edition_name(window.edition),
        "stories": len(_visible(window)),
        "updated_at": now.isoformat(),
    }


def render_index(summaries: list[dict[str, Any]], now: datetime) -> str:
    order = {c: i for i, c in enumerate(known_editions())}
    rows = sorted(summaries, key=lambda s: (order.get(s["edition"], len(order)), s["edition"]))
    editions = [{"code": s["edition"], "total": s["stories"]} for s in rows]
    return env().get_template("static_index.html").render(editions=editions, generated_at=local_dt(now))


def upload(pages: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for key, html in pages.items():
        body = html.encode()
        store.put_bytes(
            store.SITE_BUCKET,
            key,
            body,
            "text/html; charset=utf-8",
            CacheControl=f"public, max-age={CACHE_SECONDS}",
        )
        out.append(
            {
                "key": key,
                "bytes": len(body),
                "bytes_gz": len(gzip.compress(body, 6)),
                "stories": html.count('class="card story"'),
            }
        )
    return out
