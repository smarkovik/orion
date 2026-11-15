"""Window persistence (conditional S3 write), scrape state and pruning."""

import gzip
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError
from model import Article, Window, window_key
from seer_common import store
from seer_common.text import parse_utc

log = logging.getLogger("state")

WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "48"))
STATE_HOURS = int(os.environ.get("STATE_HOURS", "48"))
UNSUPPORTED = ("NotImplemented", "501")


def load_window(edition: str) -> tuple[Window, str | None]:
    store.ensure_bucket(store.RAW_BUCKET)
    try:
        resp = store.client().get_object(Bucket=store.RAW_BUCKET, Key=window_key(edition))
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return Window(edition=edition), None
        raise
    window = Window.from_json(json.loads(gzip.decompress(resp["Body"].read())))
    return window, resp["ETag"]


def save_window(window: Window, etag: str | None) -> int:
    """Conditional put: IfMatch etag, or IfNoneMatch * for a new window. A 412 raises."""
    data = gzip.compress(store.dumps(window.to_json()).encode(), 6)
    store.ensure_bucket(store.RAW_BUCKET)
    args: dict[str, Any] = {
        "Bucket": store.RAW_BUCKET,
        "Key": window_key(window.edition),
        "Body": data,
        "ContentType": "application/gzip",
    }
    cond = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
    try:
        store.client().put_object(**args, **cond)
    except ClientError as e:
        code = str(e.response.get("Error", {}).get("Code"))
        if code not in UNSUPPORTED:
            raise
        log.warning("S3 endpoint does not support conditional writes (%s); writing unconditionally", code)
        store.client().put_object(**args)
    return len(data)


def update_last_ok(window: Window, manifest: dict[str, Any]) -> None:
    started = parse_utc(manifest.get("started_at"))
    if started is None or manifest.get("truncated"):
        return
    for domain, info in (manifest.get("sources") or {}).items():
        if info and not info.get("errors") and not info.get("skipped"):
            window.source_last_ok[domain] = started


def write_scrape_state(window: Window, now: datetime) -> int:
    cutoff = now - timedelta(hours=STATE_HOURS)
    sources: dict[str, Any] = {d: {"last_ok_started_at": t.isoformat()} for d, t in window.source_last_ok.items()}
    for domain in {a.source for a in window.articles.values()}:
        sources.setdefault(domain, {})
    for info in sources.values():
        info["known"] = {}
    for a in window.articles.values():
        if a.published_at >= cutoff:
            sources[a.source]["known"][a.url] = {
                "p": a.published_at.isoformat(),
                "c": a.checked_at.isoformat() if a.checked_at else None,
                "b": bool(a.body),
            }
    state = {
        "v": 1,
        "edition": window.edition,
        "generated_at": now.isoformat(timespec="seconds"),
        "last_run_id": window.last_run_id,
        "last_run_started_at": window.last_run_started_at.isoformat() if window.last_run_started_at else None,
        "sources": sources,
    }
    return store.put_json(store.RAW_BUCKET, store.state_key(window.edition), state, gz=True)


def prune(window: Window, now: datetime) -> list[Article]:
    """Drop articles older than WINDOW_HOURS unless they belong to an open story in the window."""
    cutoff = now - timedelta(hours=WINDOW_HOURS)
    dropped = [a for a in window.articles.values() if a.published_at < cutoff and a.story_id not in window.stories]
    for a in dropped:
        del window.articles[a.url]
    return dropped
