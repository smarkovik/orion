"""Reader statistics: CloudFront logs -> per-day counts and a story catalog (see READERS.md). Never raises."""

import gzip
import html
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import parse_qs, unquote_plus
from zoneinfo import ZoneInfo

from seer_common import store
from ua import classify
from web import render as web

PREFIX = "system/admin/data/readers"
CURSOR_KEY = "state/readers_cursor.json"
KEEP_DAYS = 400
CATALOG_DAYS = 35
TIME_CAP_MS = 1_800_000
HIST_MS = (5000, 10000, 20000, 30000, 60000, 120000, 300000, 600000, 1800000)
PAGES_TOP = 200
EVENTS = {"v", "l", "o", "s", "f"}
KINDS = {"front", "section", "story", "day", "week", "briefing", "calendar", "about", "chooser"}
BOT = re.compile(r"bot|spider|crawl|slurp|preview|monitor", re.I)
PING_PATH = "/system/p.gif"
PAGE_RE = re.compile(r"^[\w./-]{1,200}\.html$")
STORY_RE = re.compile(r"^[a-z]+-\d+$")
HOST_RE = re.compile(r"^[a-z0-9.-]{1,100}$")
USED = ("date", "time", "cs-uri-stem", "cs-uri-query", "sc-status", "cs(User-Agent)")

log = logging.getLogger("readers")
Counts = dict[tuple[str, str], dict[str, Any]]


def _hist(ms: int) -> int:
    return next((i for i, hi in enumerate(HIST_MS) if ms <= hi), len(HIST_MS))


def _empty(edition: str, day: str) -> dict[str, Any]:
    return {
        "v": 1,
        "edition": edition,
        "date": day,
        "updated": "",
        "views": 0,
        "views_returning": 0,
        "server_html": 0,
        "readers_day": 0,
        "returning_day": 0,
        "first_week": 0,
        "first_month": 0,
        "kinds": {},
        "sections": {},
        "stories": {},
        "outlets": {},
        "pages": {},
        "events": {"share": 0, "follow": 0},
        "devices": {},
    }


ROWS = {
    "sections": ("views", "views_returning"),
    "stories": ("views", "views_returning", "out", "time_n", "time_sum_ms"),
    "outlets": ("out",),
}


def _bump(d: dict[str, Any], key: str, name: str, field: str, by: int = 1) -> None:
    row = d[key].setdefault(name, dict.fromkeys(ROWS[key], 0))
    row[field] += by


def _add_time(row: dict[str, Any], ms: int) -> None:
    t = row.setdefault("time", {"n": 0, "sum_ms": 0, "hist": [0] * (len(HIST_MS) + 1)})
    t["n"] += 1
    t["sum_ms"] += ms
    t["hist"][_hist(ms)] += 1


def _device(doc: dict[str, Any], ev: dict[str, Any], ret: bool) -> None:
    dev, os_, browser = classify(ev["ua"], ev["tm"])
    d = doc["devices"].setdefault(
        dev,
        {
            "views": 0,
            "views_returning": 0,
            "readers_day": 0,
            "returning_day": 0,
            "story_time": {"n": 0, "sum_ms": 0, "hist": [0] * (len(HIST_MS) + 1)},
            "os": {},
            "browsers": {},
        },
    )
    if ev["e"] == "l":
        if ev["k"] == "story":
            _add_time({"time": d["story_time"]}, ev["t"])
        return
    d["views"] += 1
    d["views_returning"] += int(ret)
    d["readers_day"] += int(ev["fd"])
    d["returning_day"] += int(ev["fd"] and ret)
    for key, name in (("os", os_), ("browsers", browser)):
        row = d[key].setdefault(name, {"views": 0, "readers_day": 0})
        row["views"] += 1
        row["readers_day"] += int(ev["fd"])


def _apply(doc: dict[str, Any], ev: dict[str, Any]) -> None:
    kind, ret, st = ev["k"], ev["n"] == "1", ev["st"]
    e = ev["e"]
    if e in ("v", "l"):
        _device(doc, ev, ret)
    if e == "v":
        doc["views"] += 1
        doc["views_returning"] += int(ret)
        k = doc["kinds"].setdefault(kind, {"views": 0, "views_returning": 0})
        k["views"] += 1
        k["views_returning"] += int(ret)
        if ev["sec"]:
            _bump(doc, "sections", ev["sec"], "views")
            _bump(doc, "sections", ev["sec"], "views_returning", int(ret))
        if st:
            _bump(doc, "stories", st, "views")
            _bump(doc, "stories", st, "views_returning", int(ret))
        doc["pages"][ev["p"]] = doc["pages"].get(ev["p"], 0) + 1
        if ev["fd"]:
            doc["readers_day"] += 1
            doc["returning_day"] += int(ret)
        doc["first_week"] += int(ev["fw"])
        doc["first_month"] += int(ev["fm"])
    elif e == "l":
        ms = ev["t"]
        _add_time(doc["kinds"].setdefault(kind, {"views": 0, "views_returning": 0}), ms)
        if st:
            _bump(doc, "stories", st, "time_n")
            _bump(doc, "stories", st, "time_sum_ms", ms)
    elif e == "o":
        if st:
            _bump(doc, "stories", st, "out")
        if ev["o"]:
            _bump(doc, "outlets", ev["o"], "out")
    elif e == "s":
        doc["events"]["share"] += 1
    elif e == "f":
        doc["events"]["follow"] += 1


def _event(q: dict[str, list[str]], editions: Mapping[str, Any]) -> dict[str, Any] | None:
    def one(name: str) -> str:
        return (q.get(name) or [""])[0]

    ed, e, kind, page = one("ed"), one("e"), one("k"), one("p")
    if one("v") != "1" or ed not in editions or e not in EVENTS or kind not in KINDS or not PAGE_RE.match(page):
        return None
    st, outlet = one("st"), one("o").lower()
    ms = 0
    if e == "l":
        if not one("t").isdigit():
            return None
        ms = min(int(one("t")), TIME_CAP_MS)
    return {
        "ed": ed,
        "e": e,
        "k": kind,
        "p": page,
        "st": st if STORY_RE.match(st) else "",
        "sec": one("sec")[:80],
        "n": "1" if one("n") == "1" else "0",
        "fd": one("fd") == "1",
        "fw": one("fw") == "1",
        "fm": one("fm") == "1",
        "tm": one("tm") == "1",
        "ua": "",
        "t": ms,
        "o": outlet if HOST_RE.match(outlet) else "",
    }


def _lines(text: str, stats: dict[str, int]) -> Iterator[dict[str, str]]:
    cols: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith("#"):
            if line.startswith("#Fields:"):
                names = line[8:].split()
                cols = {n: names.index(n) for n in USED if n in names}
            continue
        if not line or len(cols) < len(USED):
            continue
        parts = line.split("\t")
        try:
            yield {n: parts[i] for n, i in cols.items()}
        except IndexError:
            stats["bad"] += 1


def _aggregate(text: str, cfg: dict[str, Any], counts: Counts, stats: dict[str, int], tzs: dict[str, ZoneInfo]) -> None:
    editions = cfg["editions"]
    for row in _lines(text, stats):
        stats["lines"] += 1
        path = row["cs-uri-stem"]
        if path != PING_PATH and not (path.endswith(".html") and row["sc-status"] == "200"):
            continue
        if BOT.search(unquote_plus(row["cs(User-Agent)"])):
            stats["bots"] += 1
            continue
        try:
            when = datetime.fromisoformat(f"{row['date']}T{row['time']}").replace(tzinfo=timezone.utc)
        except ValueError:
            stats["bad"] += 1
            continue
        if path == PING_PATH:
            ev = _event(parse_qs(row["cs-uri-query"]), editions)
            if ev is None:
                stats["bad"] += 1
                continue
            ev["ua"] = row["cs(User-Agent)"]
            edition = ev["ed"]
        else:
            edition = path.lstrip("/").split("/", 1)[0]
            if edition not in editions:
                continue
            ev = None
        if edition not in tzs:
            tzs[edition] = ZoneInfo(editions[edition]["timezone"])
        tz = tzs[edition]
        day = when.astimezone(tz).date().isoformat()
        doc = counts.setdefault((edition, day), _empty(edition, day))
        if ev is None:
            doc["server_html"] += 1
            stats["html"] += 1
        else:
            _apply(doc, ev)
            stats["pings"] += 1


def _decode(raw: bytes, name: str) -> str:
    if name.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


class _Local:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def names(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())

    def read(self, name: str) -> bytes:
        return (self.root / name).read_bytes()

    def delete(self, name: str) -> None:
        (self.root / name).unlink(missing_ok=True)


class _S3:
    def __init__(self, bucket: str, prefix: str) -> None:
        self.bucket, self.prefix = bucket, prefix

    def names(self) -> list[str]:
        out: list[str] = []
        pages = store.client().get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix)
        for page in pages:
            out += [o["Key"] for o in page.get("Contents", []) if not o["Key"].endswith("/")]
        return sorted(out)

    def read(self, name: str) -> bytes:
        return store.client().get_object(Bucket=self.bucket, Key=name)["Body"].read()

    def delete(self, name: str) -> None:
        store.client().delete_object(Bucket=self.bucket, Key=name)


def _source() -> _Local | _S3:
    local = os.environ.get("LOGS_DIR")
    if local:
        return _Local(local)
    bucket = os.environ.get("LOGS_BUCKET") or store.RAW_BUCKET
    return _S3(bucket, os.environ.get("LOGS_PREFIX", "logs/cloudfront/"))


def _merge(old: Any, new: Any) -> Any:
    if isinstance(new, dict):
        base = old if isinstance(old, dict) else {}
        return {k: _merge(base.get(k), v) for k, v in new.items()} | {k: v for k, v in base.items() if k not in new}
    if isinstance(new, list):
        base = old if isinstance(old, list) and len(old) == len(new) else [0] * len(new)
        return [a + b for a, b in zip(base, new)]
    if isinstance(new, (int, float)) and not isinstance(new, bool):
        return (old if isinstance(old, (int, float)) else 0) + new
    return new


def _write_days(counts: Counts, now: datetime) -> dict[str, set[str]]:
    touched: dict[str, set[str]] = defaultdict(set)
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    for (edition, day), fresh in sorted(counts.items()):
        key = f"{PREFIX}/{edition}/{day}.json"
        old = store.get_json(store.SITE_BUCKET, key)
        doc = _merge(old, {k: v for k, v in fresh.items() if k not in ("v", "edition", "date", "updated")})
        doc.update({"v": 1, "edition": edition, "date": day, "updated": stamp})
        pages = sorted(doc["pages"].items(), key=lambda kv: -kv[1])[:PAGES_TOP]
        doc["pages"] = dict(pages)
        store.put_bytes(store.SITE_BUCKET, key, store.dumps(doc).encode(), "application/json", CacheControl="no-cache")
        touched[edition].add(day)
    return touched


def _write_index(editions: Mapping[str, Any], now: datetime) -> None:
    """Rebuilt from a listing of the day files, so a lost or broken index heals on the next run."""
    cutoff = (now - timedelta(days=KEEP_DAYS)).date().isoformat()
    pager = store.client().get_paginator("list_objects_v2")
    eds: dict[str, Any] = {}
    for edition in editions:
        days = {
            o["Key"].rsplit("/", 1)[1].removesuffix(".json")
            for page in pager.paginate(Bucket=store.SITE_BUCKET, Prefix=f"{PREFIX}/{edition}/")
            for o in page.get("Contents", [])
            if o["Key"].endswith(".json")
        }
        if days:
            eds[edition] = {"days": sorted((d for d in days if d >= cutoff), reverse=True)}
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    body = store.dumps({"updated": stamp, "editions": eds}).encode()
    key = f"{PREFIX}/index.json"
    store.put_bytes(store.SITE_BUCKET, key, body, "application/json", CacheControl="no-cache")


def _catalog(cfg: dict[str, Any], now: datetime, windows: Mapping[str, Any]) -> int:
    key = f"{PREFIX}/stories.json"
    old = (store.get_json(store.SITE_BUCKET, key) or {}).get("stories") or {}
    cutoff = (now - timedelta(days=CATALOG_DAYS)).isoformat()
    stories = {k: v for k, v in old.items() if v["first_published"] >= cutoff}
    for code, window in windows.items():
        ecfg = {**cfg, "edition": code}
        for s in window.stories.values():
            label = window.articles.get(s.label_url or "")
            if s.source_count < 2 or label is None or s.first_published.isoformat() < cutoff:
                continue
            arts = [window.articles[u] for u in s.members if u in window.articles]
            stories[s.id] = {
                "edition": code,
                "title": html.unescape(label.title),
                "section": web._facet(s, ecfg) or web._ed(ecfg)["name"],
                "sources": s.source_count,
                "outlets": list(dict.fromkeys(a.source for a in arts)),
                "first_published": s.first_published.isoformat(),
                "page": f"{code}/story/{web._num(s)}.html",
            }
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    body = store.dumps({"updated": stamp, "stories": stories}).encode()
    store.put_bytes(store.SITE_BUCKET, key, body, "application/json", CacheControl="no-cache")
    return len(stories)


def process(cfg: dict[str, Any], now: datetime, windows: Mapping[str, Any]) -> dict[str, Any]:
    """Count new log files, write the day files and the story catalog, delete the logs. Never raises."""
    stats: dict[str, Any] = {"files": 0, "lines": 0, "pings": 0, "html": 0, "bots": 0, "bad": 0, "deleted": 0}
    try:
        stats["catalog"] = _catalog(cfg, now, windows)
    except Exception as e:  # noqa: BLE001
        log.exception("readers catalog failed")
        stats["catalog_error"] = repr(e)
    try:
        src = _source()
        cursor = store.get_json(store.RAW_BUCKET, CURSOR_KEY) or {}
        done = set(cursor.get("done") or [])
        names = src.names()
        todo = [n for n in names if n not in done]
        counts: Counts = {}
        tzs: dict[str, ZoneInfo] = {}
        read: list[str] = []
        for name in todo:
            try:
                _aggregate(_decode(src.read(name), name), cfg, counts, stats, tzs)
                read.append(name)
            except Exception:  # noqa: BLE001 - an unreadable file is left for the next run
                log.exception("readers: cannot read %s", name)
                stats["unreadable"] = stats.get("unreadable", 0) + 1
        stats["files"] = len(read)
        if counts:
            _write_days(counts, now)
            stats["days"] = len(counts)
        if read:
            done |= set(read)
            store.put_json(store.RAW_BUCKET, CURSOR_KEY, {"done": sorted(done)})
            for name in read:
                try:
                    src.delete(name)
                    stats["deleted"] += 1
                except Exception:  # noqa: BLE001
                    log.exception("readers: cannot delete %s", name)
        left = sorted(done & set(src.names()))
        if left != sorted(cursor.get("done") or []):
            store.put_json(store.RAW_BUCKET, CURSOR_KEY, {"done": left})
    except Exception as e:  # noqa: BLE001
        log.exception("readers failed")
        stats["error"] = repr(e)
    if stats.get("days"):
        try:
            _write_index(cfg["editions"], now)
        except Exception as e:  # noqa: BLE001
            log.exception("readers index failed")
            stats["index_error"] = repr(e)
    return stats
