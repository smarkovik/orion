import gzip
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

import stories_data as sd
from seer_common import store

TEMPLATES = Path(os.environ.get("TEMPLATES_DIR", Path(__file__).parent / "templates"))
CACHE_SECONDS = int(os.environ.get("SITE_CACHE_SECONDS", "300"))
LIMITS = {"top": int(os.environ.get("TOP_LIMIT", "60")), "latest": int(os.environ.get("LATEST_LIMIT", "60"))}
PAGES = {"top": "index.html", "latest": "latest.html"}
MIN_SOURCES = int(os.environ.get("MIN_SOURCES", "2"))

env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
env.filters["local_dt"] = sd.local_dt
env.filters["safe_url"] = sd.safe_url
env.filters["edition_name"] = sd.edition_name


def upload(key: str, html: str, stories: int) -> dict[str, Any]:
    body = html.encode()
    store.put_bytes(
        store.SITE_BUCKET,
        key,
        body,
        "text/html; charset=utf-8",
        CacheControl=f"public, max-age={CACHE_SECONDS}",
    )
    return {"key": key, "bytes": len(body), "bytes_gz": len(gzip.compress(body, 6)), "stories": stories}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    start = time.perf_counter()
    available = sd.story_editions()
    editions = (event or {}).get("editions") or available
    generated_at = datetime.now(sd.TZ).strftime("%Y-%m-%d %H:%M")
    pages: list[dict[str, Any]] = []
    summary = []
    for code in editions:
        regions = sd.story_facets(code, "region", MIN_SOURCES)
        subjects = sd.story_facets(code, "subject", MIN_SOURCES)
        total = sum(f["n"] for f in regions)
        summary.append({"code": code, "total": total})
        for view, name in PAGES.items():
            stories, members = sd.load_stories(code, view, MIN_SOURCES)
            stories = stories[: LIMITS[view]]
            html = env.get_template("static_page.html").render(
                edition=code,
                editions=editions,
                view=view,
                views=list(PAGES),
                pages=PAGES,
                stories=stories,
                members=members,
                regions=regions,
                subjects=subjects,
                total=total,
                min_sources=MIN_SOURCES,
                none_value=sd.NONE,
                generated_at=generated_at,
            )
            pages.append(upload(f"{code}/{name}", html, len(stories)))
    html = env.get_template("static_index.html").render(editions=summary, generated_at=generated_at)
    pages.append(upload("index.html", html, 0))
    return {"pages": pages, "duration_s": round(time.perf_counter() - start, 2)}
