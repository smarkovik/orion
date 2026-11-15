"""Per-edition day index (state/{edition}/days.json): per day the lead story and top list, newest first."""

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from model import Window, days_key
from seer_common import store
from web import render as web_render

KEEP_DAYS = 3 * 365


def load(edition: str) -> list[dict[str, Any]]:
    doc = store.get_json(store.RAW_BUCKET, days_key(edition))
    return list((doc or {}).get("days") or [])


def save(edition: str, days: list[dict[str, Any]], now: datetime) -> int:
    doc = {"v": 1, "edition": edition, "updated_at": now.isoformat(), "days": days}
    return store.put_json(store.RAW_BUCKET, days_key(edition), doc)


def _entry(window: Window, cfg: dict[str, Any], day: date) -> dict[str, Any]:
    stories = web_render.day_stories(window, day, cfg)
    lead = stories[0] if stories else None
    label = window.articles.get(lead.label_url or "") if lead else None
    return {
        "date": day.isoformat(),
        "stories": len(web_render.day_stories(window, day, cfg, limit=False)),
        "lead_title": label.title if label else "",
        "lead_story": lead.id if lead else "",
        "lead_thumb": (lead.thumb_key or "") if lead else "",
        "top": [web_render.story_summary(window, s, cfg) for s in stories[: cfg["limits"].get("week", 10)]],
    }


def update(window: Window, cfg: dict[str, Any], now: datetime, previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tz = ZoneInfo(cfg["editions"][cfg["edition"]]["timezone"])
    today = now.astimezone(tz).date()
    by_date = {d["date"]: d for d in previous}
    for day in web_render.live_dates(window, cfg, now, previous):
        new = _entry(window, cfg, day)
        old = by_date.get(new["date"])
        # Closed stories leave the window, so a recomputed past day may only shrink: keep the fuller entry.
        if day != today and old and old.get("stories", 0) > new["stories"]:
            continue
        if new["stories"] or old:
            by_date[new["date"]] = new
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    return sorted((d for d in by_date.values() if d["date"] >= cutoff), key=lambda d: d["date"], reverse=True)
