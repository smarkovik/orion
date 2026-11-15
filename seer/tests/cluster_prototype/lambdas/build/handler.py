"""Build: ingest one scrape batch into the edition window, cluster, render, persist."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import unquote_plus

import archive
import days
import ingest
import render
import state
import stories
import thumbs
import yaml
from categories import CategoryMap
from model import summary_key, build_report_key
from seer_common import store
from seer_common.text import parse_utc
from web import render as web

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("build")


def _manifest_key(event: dict[str, Any]) -> str:
    if event.get("manifest_key"):
        return event["manifest_key"]
    return unquote_plus(event["Records"][0]["s3"]["object"]["key"])


def _upload_pages(pages: list[Any]) -> dict[str, int]:
    """Upload site pages; assets and thumbnails are immutable, so an existing key is left alone."""

    def put(page: Any) -> int | None:
        if page.key.startswith("assets/") and thumbs.exists(page.key):
            return None
        return store.put_bytes(
            store.SITE_BUCKET, page.key, page.body, page.content_type, CacheControl=page.cache_control
        )

    with ThreadPoolExecutor(8) as pool:
        sizes = list(pool.map(put, pages))
    sent = [n for n in sizes if n is not None]
    return {"count": len(sent), "skipped": len(sizes) - len(sent), "bytes": sum(sent)}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    t_start = time.perf_counter()
    ratio = float(os.environ.get("CHANGE_MIN_RATIO", "0.05"))
    timings: dict[str, float] = {}

    def lap(name: str, since: float) -> float:
        t = time.perf_counter()
        timings[name] = round(t - since, 2)
        return t

    manifest_key = _manifest_key(event)
    manifest = store.get_json(store.RAW_BUCKET, manifest_key)
    if manifest is None:
        raise FileNotFoundError(manifest_key)
    edition, run_id = manifest["edition"], manifest["run_id"]
    started = parse_utc(manifest["started_at"])
    assert started is not None
    # The scrape's own clock, so a replayed run builds exactly what the live run built.
    now = parse_utc(event.get("now")) or parse_utc(manifest.get("finished_at")) or started
    with open(os.environ.get("SOURCES_FILE", "/var/task/sources.yaml"), encoding="utf-8") as f:
        editions = yaml.safe_load(f)["editions"]
    if edition not in editions:
        raise ValueError(f"unknown edition {edition!r}")
    domains = {s["domain"] for s in editions[edition]["sources"]}

    t = time.perf_counter()
    window, etag = state.load_window(edition)
    t = lap("load", t)
    if window.last_run_started_at and started <= window.last_run_started_at:
        reason = f"started_at {started.isoformat()} not newer than {window.last_run_started_at.isoformat()}"
        log.info("%s %s skipped: %s", edition, run_id, reason)
        return {"edition": edition, "run_id": run_id, "skipped": reason}

    full_bodies: dict[str, str] = {}
    counts, touched = ingest.apply_batch(
        window,
        store.iter_jsonl_gz(store.RAW_BUCKET, manifest["raw_key"]),
        ratio,
        now,
        full_bodies=full_bodies,
        domains=domains,
    )
    state.update_last_ok(window, manifest)
    window.last_run_id, window.last_run_started_at = run_id, started
    t = lap("ingest", t)

    embedded, embed_s = stories.embed_new(window)
    t = lap("embed", t)

    with open(os.environ.get("CATEGORIES_FILE", "/var/task/categories.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    story_counts, touched_story_ids, closed = stories.assign(window, CategoryMap(cfg, edition), now)
    closed_ids = {s.id for s in closed}
    for sid in closed_ids:
        window.stories.pop(sid, None)
    arch_articles = [window.articles[u] for u in sorted(touched) if u in window.articles]
    dropped = state.prune(window, now)
    story_counts = {**story_counts, "open": len(window.stories)}
    t = lap("assign", t)

    with open(os.environ.get("SITE_FILE", "/var/task/site.yaml"), encoding="utf-8") as f:
        site_cfg = {**yaml.safe_load(f), "edition": edition}
    names = {s["domain"]: s.get("name", s["domain"]) for s in editions[edition]["sources"]}
    shown = set(web.selection(window, site_cfg, now)) | set(touched_story_ids)
    thumb_counts = thumbs.ensure(window, shown, now)
    t = lap("thumbs", t)
    day_index = days.update(window, site_cfg, now, days.load(edition))
    t = lap("days", t)

    summary = render.edition_summary(window, now)
    summaries = []
    for e in editions:
        s = summary if e == edition else store.get_json(store.RAW_BUCKET, summary_key(e))
        if s:
            summaries.append(s)
    asset_pages, _, _ = web.render_assets(site_cfg)
    site_pages = [
        *asset_pages,
        *web.render_edition(window, site_cfg, now, day_index, names, set(touched_story_ids)),
        *web.render_root(site_cfg, summaries, now),
    ]
    lab_pages = render.render_edition(window, now)
    lab_pages[f"{render.LAB}/index.html"] = render.render_index(summaries, now)
    uploaded = render.upload(lab_pages)
    site_uploaded = _upload_pages(site_pages)
    t = lap("render", t)

    store.put_json(store.RAW_BUCKET, summary_key(edition), summary)
    arch_stories = [window.stories[i] for i in touched_story_ids if i in window.stories] + list(closed)
    arch_key, arch_bytes = archive.write_archive(
        edition,
        run_id,
        started,
        arch_articles,
        arch_stories,
        full_bodies=full_bodies,
        closed_ids=closed_ids,
    )
    window_bytes = state.save_window(window, etag)
    days_bytes = days.save(edition, day_index, now)
    state.write_scrape_state(window, now)
    t = lap("save", t)

    out = {
        "edition": edition,
        "run_id": run_id,
        **{k: counts[k] for k in ("inserted", "updated", "changed", "refreshed", "failures")},
        "embedded": embedded,
        "embed_s": round(embed_s, 2),
        "stories": story_counts,
        "thumbs": thumb_counts,
        "days": {"entries": len(day_index), "bytes": days_bytes},
        "site_pages": site_uploaded,
        "pages": uploaded,
        "window_bytes": window_bytes,
        "archive_bytes": arch_bytes,
        "pruned": len(dropped),
        "timings": timings,
        "duration_s": round(time.perf_counter() - t_start, 2),
    }
    store.put_json(store.RAW_BUCKET, build_report_key(edition, run_id), out)
    log.info("build %s: %s", run_id, out)
    return out
