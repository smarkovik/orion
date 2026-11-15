"""Story thumbnails: download the best image, cover-crop to 16:9, store as WebP in the site bucket."""

import hashlib
import io
import logging
import os
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from botocore.exceptions import ClientError
from model import Article, Story, Window
from PIL import Image, ImageOps
from seer_common import store

log = logging.getLogger("thumbs")

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
WIDTH, HEIGHT, QUALITY = 640, 360, 72
MAX_BYTES = 8 * 1024 * 1024
WORKERS = 8
PER_HOST = 2
CACHE = "public, max-age=31536000, immutable"
Image.MAX_IMAGE_PIXELS = 60_000_000


def key_for(src: str) -> str:
    return f"thumbs/{hashlib.sha1(src.encode()).hexdigest()[:16]}.webp"


def _host(url: str) -> str:
    return urlsplit(url).hostname or ""


def exists(key: str) -> bool:
    try:
        store.client().head_object(Bucket=store.SITE_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def _download(client: httpx.Client, url: str) -> bytes:
    with client.stream("GET", url) as r:
        r.raise_for_status()
        if not r.headers.get("content-type", "").lower().startswith("image/"):
            raise ValueError("not an image")
        if int(r.headers.get("content-length") or 0) > MAX_BYTES:
            raise ValueError("too large")
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise ValueError("too large")
        return bytes(buf)


def _convert(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGBA" if im.mode == "P" or "A" in im.getbands() else "RGB")
        im = ImageOps.fit(im, (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=QUALITY, method=4)
        return out.getvalue()


def _candidates(story: Story, window: Window) -> list[Article]:
    arts = [window.articles[u] for u in story.members if u in window.articles and window.articles[u].image_url]
    label = [a for a in arts if a.url == story.label_url]
    rest = sorted((a for a in arts if a.url != story.label_url), key=lambda a: a.published_at, reverse=True)
    return label + rest


class _Hosts:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sems: dict[str, threading.BoundedSemaphore] = defaultdict(lambda: threading.BoundedSemaphore(PER_HOST))

    def sem(self, host: str) -> threading.BoundedSemaphore:
        with self._lock:
            return self._sems[host]


def ensure(window: Window, story_ids: list[str] | set[str], now: datetime) -> dict[str, int]:
    """Set thumb_key/thumb_src/thumb_source on stories that have none. Returns counts."""
    cap = int(os.environ.get("THUMBS_PER_RUN", "80"))
    counts = {"fetched": 0, "reused": 0, "failed": 0, "skipped": 0}
    todo = [window.stories[i] for i in story_ids if i in window.stories and window.stories[i].thumb_key is None]
    if not todo:
        return counts
    todo.sort(key=lambda s: (s.score, s.first_published), reverse=True)
    budget = [cap]
    lock = threading.Lock()
    hosts = _Hosts()
    reuse_seen: dict[str, bool] = {}
    bad: set[str] = set()

    def attempt(client: httpx.Client, story: Story) -> str:
        for art in _candidates(story, window):
            src = art.image_url or ""
            if not src.lower().startswith(("http://", "https://")) or src in bad:
                continue
            key = key_for(src)
            with lock:
                known = reuse_seen.get(key)
            if known is None:
                known = exists(key)
                with lock:
                    reuse_seen[key] = known
            if known:
                story.thumb_key, story.thumb_src, story.thumb_source = key, src, art.source
                return "reused"
            with lock:
                if budget[0] <= 0:
                    return "skipped"
                budget[0] -= 1
            try:
                with hosts.sem(_host(src)):
                    data = _download(client, src)
                webp = _convert(data)
                store.put_bytes(store.SITE_BUCKET, key, webp, "image/webp", CacheControl=CACHE)
            except Exception as e:
                log.info("thumb failed %s: %s", src, e)
                with lock:
                    counts["failed"] += 1
                    bad.add(src)
                continue
            with lock:
                reuse_seen[key] = True
            story.thumb_key, story.thumb_src, story.thumb_source = key, src, art.source
            return "fetched"
        story.thumb_key = ""
        return "none"

    with (
        httpx.Client(headers={"User-Agent": UA, "Accept": "image/*"}, timeout=10.0, follow_redirects=True) as client,
        ThreadPoolExecutor(WORKERS) as pool,
    ):

        def run(story: Story) -> str:
            try:
                return attempt(client, story)
            except Exception as e:
                log.warning("thumb story %s: %s", story.id, e)
                with lock:
                    counts["failed"] += 1
                return "error"

        for outcome in pool.map(run, todo):
            if outcome in ("fetched", "reused", "skipped"):
                counts[outcome] += 1
    log.info("thumbs %s", counts)
    return counts
