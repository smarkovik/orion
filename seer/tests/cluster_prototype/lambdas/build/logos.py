"""Outlet logos: the best icon of each homepage as a 64x64 PNG in the site bucket, refreshed rarely."""

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageOps
from seer_common import store

log = logging.getLogger("logos")

UA = "Mozilla/5.0 (compatible; SeerBot/0.1; research prototype)"
STATE_KEY = "state/logos.json"
SIZE = 64
MAX_BYTES = 2 * 1024 * 1024
REFRESH = timedelta(days=30)
RETRY = timedelta(days=7)
CACHE = "public, max-age=2592000"
LAST: dict[str, int] = {"fetched": 0, "failed": 0, "ok": 0}  # counts of the latest ensure() call


def key_for(domain: str) -> str:
    return f"logos/{domain}.png"


class _Icons(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[int, int, str]] = []  # (rank, edge, href)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel, href = a.get("rel", "").lower().split(), a.get("href", "")
        if not href or href.startswith("data:"):
            return
        edge = max((int(n) for n in a.get("sizes", "").lower().replace("x", " ").split() if n.isdigit()), default=0)
        if "apple-touch-icon" in rel or "apple-touch-icon-precomposed" in rel:
            self.found.append((2, edge, href))
        elif "icon" in rel:
            self.found.append((1, edge, href))


def _candidates(html: str, base: str) -> list[str]:
    parser = _Icons()
    try:
        parser.feed(html[:400_000])
    except Exception:  # noqa: BLE001 - broken markup still yields what was parsed
        pass
    ranked = sorted(parser.found, key=lambda x: (x[0], x[1]), reverse=True)
    urls = [urljoin(base, h) for _, _, h in ranked if not h.lower().split("?")[0].endswith(".svg")]
    urls.append(urljoin(base, "/favicon.ico"))
    return list(dict.fromkeys(urls))


def _convert(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        if im.format == "ICO" and getattr(im, "ico", None):
            im.size = max(im.ico.sizes())
        im = ImageOps.exif_transpose(im).convert("RGBA")
        if min(im.size) < 16:
            raise ValueError("too small")
        if im.getchannel("A").getextrema()[1] == 0:
            raise ValueError("blank")
        im = ImageOps.contain(im, (SIZE, SIZE), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2))
        out = io.BytesIO()
        canvas.save(out, "PNG", optimize=True)
        return out.getvalue()


def _fetch_logo(client: httpx.Client, base_url: str) -> bytes:
    home = client.get(base_url, headers={"Accept": "text/html"})
    home.raise_for_status()
    last: Exception = ValueError("no icon")
    for url in _candidates(home.text, str(home.url)):
        try:
            r = client.get(url, headers={"Accept": "image/*"})
            r.raise_for_status()
            if len(r.content) > MAX_BYTES:
                raise ValueError("too large")
            return _convert(r.content)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def _due(entry: dict[str, Any] | None, now: datetime) -> bool:
    if not entry:
        return True
    try:
        at = datetime.fromisoformat(entry["fetched_at"])
    except (KeyError, ValueError):
        return True
    return now - at >= (REFRESH if entry.get("ok") else RETRY)


def ensure(sources: dict[str, str], now: datetime) -> dict[str, str | None]:
    """Logo key per outlet domain (None when it has none). Network only for outlets that are due. Never raises."""
    try:
        state: dict[str, Any] = store.get_json(store.RAW_BUCKET, STATE_KEY) or {}
    except Exception as e:  # noqa: BLE001
        log.warning("logos state: %s", e)
        state = {}
    todo = [d for d in sources if _due(state.get(d), now)]
    LAST.update(fetched=0, failed=0, ok=0)
    if todo:

        def one(domain: str) -> tuple[str, bool]:
            try:
                png = _fetch_logo(client, sources[domain])
                store.put_bytes(store.SITE_BUCKET, key_for(domain), png, "image/png", CacheControl=CACHE)
                return domain, True
            except Exception as e:  # noqa: BLE001
                log.info("logo %s failed: %s", domain, e)
                return domain, False

        try:
            with (
                httpx.Client(headers={"User-Agent": UA}, timeout=10.0, follow_redirects=True) as client,
                ThreadPoolExecutor(8) as pool,
            ):
                for domain, ok in pool.map(one, todo):
                    LAST["fetched" if ok else "failed"] += 1
                    prev = state.get(domain) or {}
                    # a failed refresh keeps the logo already stored
                    state[domain] = {"fetched_at": now.isoformat(), "ok": ok or (prev.get("ok") is True)}
            store.put_json(store.RAW_BUCKET, STATE_KEY, state)
        except Exception as e:  # noqa: BLE001
            log.warning("logos: %s", e)
    result = {d: (key_for(d) if (state.get(d) or {}).get("ok") else None) for d in sources}
    LAST["ok"] = sum(v is not None for v in result.values())
    return result
