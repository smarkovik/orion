"""Back-office data: one compact summary per run, appended to per-day JSON files read by the static admin page."""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from model import Window
from seer_common import store

log = logging.getLogger("admin")

HERE = Path(__file__).parent / "web" / "admin"
STATIC = (
    ("index.html", "text/html; charset=utf-8"),
    ("admin.css", "text/css; charset=utf-8"),
    ("admin.js", "text/javascript; charset=utf-8"),
)
KEEP_DAYS = 400
BUCKETS = (("1", 1, 1), ("2", 2, 2), ("3-4", 3, 4), ("5-9", 5, 9), ("10+", 10, 10**9))
# PUT/GET calls outside the page uploads: window, days, state, archive, report, summary, admin day file and index
FIXED_PUT = {"scrape": 3, "build": 8}
FIXED_GET = {"scrape": 1, "build": 6}
TITLE_MAX = 80


def _buckets(values: list[int]) -> dict[str, int]:
    return {name: sum(lo <= v <= hi for v in values) for name, lo, hi in BUCKETS}


def _title(window: Window, story: Any) -> str:
    art = window.articles.get(story.label_url or "")
    text = re.sub(r"\s+", " ", art.title if art else "").strip()
    return text[:TITLE_MAX]


def cost(build: dict[str, Any], scrape_s: float, build_s: float, cfg: dict[str, Any]) -> dict[str, Any]:
    a = cfg["admin"]
    p, mem = a["pricing"], a["memory_mb"]
    gb_s = scrape_s * mem["scrape"] / 1024 + build_s * mem["build"] / 1024
    lambda_usd = gb_s * p["lambda_gb_s"] + 2 * p["lambda_per_million"] / 1e6
    puts = build.get("puts", 0) + FIXED_PUT["scrape"] + FIXED_PUT["build"]
    gets = build.get("gets", 0) + FIXED_GET["scrape"] + FIXED_GET["build"]
    s3_usd = puts / 1000 * p["s3_put_per_1k"] + gets / 1000 * p["s3_get_per_1k"]
    added = {k: int(v) for k, v in build.get("storage", {}).items()}
    months = a["retention_days"] / 30
    raw_months = min(180, a["retention_days"]) / 30
    std_gb = sum(v for k, v in added.items() if k != "raw") / 1e9 * months + added.get("raw", 0) / 1e9 * raw_months
    deep_gb = added.get("raw", 0) / 1e9 * (months - raw_months)
    storage_usd = std_gb * p["s3_storage_gb_month"] + deep_gb * p["s3_deep_gb_month"]
    return {
        "lambda_gb_s": round(gb_s, 1),
        "lambda_usd": round(lambda_usd, 6),
        "s3_put": puts,
        "s3_get": gets,
        "s3_usd": round(s3_usd, 6),
        "storage_bytes": added,
        "storage_gb_month": round(std_gb + deep_gb, 6),
        "storage_usd": round(storage_usd, 6),
        "total_usd": round(lambda_usd + s3_usd + storage_usd, 6),
    }


def summary(
    manifest: dict[str, Any], window: Window, now: datetime, build: dict[str, Any], cfg: dict[str, Any]
) -> dict[str, Any]:
    """`build` holds the handler's counters: counts, embedded, stories, timings, thumbs, logos, site, pages, bytes."""
    started = datetime.fromisoformat(manifest["started_at"])
    finished = datetime.fromisoformat(manifest["finished_at"]) if manifest.get("finished_at") else started
    scrape_s = round((finished - started).total_seconds(), 1)
    build_s = round(build["build_s"], 1)
    new_by_source: dict[str, int] = {}
    for art in window.articles.values():
        if art.first_seen_at >= started:
            new_by_source[art.source] = new_by_source.get(art.source, 0) + 1
    sources = {
        d: {
            "listed": s.get("listed", 0),
            "fetched": s.get("fetched", 0),
            "refresh": s.get("refresh", 0),
            "failures": s.get("failures", 0),
            "errors": s.get("errors", 0),
            "skipped": int(bool(s.get("skipped"))),
            "new": new_by_source.get(d, 0),
        }
        for d, s in manifest.get("sources", {}).items()
    }
    open_stories = list(window.stories.values())
    top = sorted(open_stories, key=lambda s: (-s.size, s.id))[:5]
    st = build["stories"]
    errors = sum(s["errors"] for s in sources.values())
    out = {
        "run_id": manifest["run_id"],
        "edition": manifest["edition"],
        "ok": errors == 0 and not manifest.get("truncated"),
        "scrape_started": manifest["started_at"],
        "scrape_finished": manifest.get("finished_at"),
        "built_at": now.isoformat(timespec="seconds"),
        "scrape_s": scrape_s,
        "build_s": build_s,
        "timings": build["timings"],
        "scrape": {
            "records": manifest.get("records", 0),
            "bytes_raw": manifest.get("bytes_raw", 0),
            "bytes_gz": manifest.get("bytes_gz", 0),
            "truncated": bool(manifest.get("truncated")),
            "sources": sources,
        },
        "build": {k: build["counts"][k] for k in ("inserted", "updated", "changed", "refreshed", "failures")}
        | {"embedded": build["embedded"]},
        "stories": {
            **{k: st.get(k, 0) for k in ("open", "multi_source", "new", "joined", "updated", "closed")},
            "largest": top[0].size if top else 0,
            "size_buckets": _buckets([s.size for s in open_stories]),
            "sources_buckets": _buckets([s.source_count for s in open_stories]),
            "top": [[s.id, s.size, s.source_count, _title(window, s)] for s in top],
        },
        "site": {
            "pages": build["site"]["count"],
            "page_bytes": build["site"]["bytes"],
            "thumbs": build["thumbs"],
            "logos": build["logos"],
            "window_bytes": build["window_bytes"],
            "archive_bytes": build["archive_bytes"],
            "days_entries": build["days_entries"],
        },
    }
    out["cost"] = cost(build, scrape_s, build_s, cfg)
    return out


def _day(cfg: dict[str, Any], edition: str, now: datetime) -> str:
    tz = ZoneInfo(cfg["editions"][edition]["timezone"])
    return now.astimezone(tz).date().isoformat()


def fixed_monthly(cfg: dict[str, Any]) -> float:
    return round(sum(cfg["admin"]["pricing"]["fixed_monthly"].values()), 2)


def cloudfront_month(cfg: dict[str, Any]) -> dict[str, float]:
    a = cfg["admin"]
    p = a["pricing"]["cloudfront"]
    views = a["assumed_views_month"]
    gb = views * (a["page_kb"] + a["images_per_view"] * a["thumb_kb"]) / 1e6
    reqs = views * (1 + a["images_per_view"])
    list_usd = gb * p["gb"] + reqs / 10_000 * p["per_10k_https"]
    # CloudFront's free allowance is permanent, not a 12-month trial.
    usd = (
        max(0.0, gb - p.get("free_gb", 0)) * p["gb"]
        + max(0, reqs - p.get("free_requests", 0)) / 10_000 * p["per_10k_https"]
    )
    return {"gb": round(gb, 1), "requests": reqs, "usd": round(usd, 2), "list_usd": round(list_usd, 2)}


def record(edition: str, run: dict[str, Any], cfg: dict[str, Any], now: datetime) -> int:
    """Append the run to its day file and rewrite the index. Returns the number of PUTs made. Never raises."""
    try:
        day = _day(cfg, edition, now)
        key = f"admin/data/{edition}/{day}.json"
        doc = store.get_json(store.SITE_BUCKET, key) or {"edition": edition, "date": day, "runs": []}
        doc["runs"] = [r for r in doc["runs"] if r.get("run_id") != run["run_id"]] + [run]
        store.put_bytes(store.SITE_BUCKET, key, store.dumps(doc).encode(), "application/json", CacheControl="no-cache")
        index = store.get_json(store.SITE_BUCKET, "admin/data/index.json") or {}
        eds = index.get("editions") or {}
        cutoff = (now - timedelta(days=KEEP_DAYS)).date().isoformat()
        days = sorted({*(eds.get(edition) or {}).get("days", []), day}, reverse=True)
        eds[edition] = {
            "name": cfg["editions"][edition]["name"],
            "tz": cfg["editions"][edition]["timezone"],
            "days": [d for d in days if d >= cutoff],
            "last_run": {"run_id": run["run_id"], "at": run["built_at"], "ok": run["ok"]},
        }
        index = {
            "generated": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "brand": cfg["brand"]["name"],
            "editions": {c: eds[c] for c in cfg["editions"] if c in eds},
            "fixed_month_usd": fixed_monthly(cfg),
            "cloudfront_month": cloudfront_month(cfg),
            "assumed_views_month": cfg["admin"]["assumed_views_month"],
        }
        store.put_bytes(
            store.SITE_BUCKET,
            "admin/data/index.json",
            store.dumps(index).encode(),
            "application/json",
            CacheControl="no-cache",
        )
        return 2
    except Exception:  # noqa: BLE001 - the admin data must never fail the build
        log.exception("admin record failed")
        return 0


def publish_static() -> int:
    """Upload the admin page files that changed (ETag = md5 for single-part objects). Never raises."""
    sent = 0
    for name, ctype in STATIC:
        try:
            body = (HERE / name).read_bytes()
            try:
                etag = store.client().head_object(Bucket=store.SITE_BUCKET, Key=f"admin/{name}")["ETag"].strip('"')
            except Exception:  # noqa: BLE001
                etag = ""
            if etag == hashlib.md5(body).hexdigest():  # noqa: S324 - change detection only
                continue
            store.put_bytes(store.SITE_BUCKET, f"admin/{name}", body, ctype, CacheControl="no-cache")
            sent += 1
        except Exception:  # noqa: BLE001
            log.exception("admin static %s failed", name)
    return sent
