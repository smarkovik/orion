"""Control Lambda behind CloudFront at /system/control/: start a sync and read Lambda cost from the CloudWatch logs.

POST .../sync  starts one scrape of every edition (it starts one build), within a cooldown and a daily limit.
GET  .../cost  billed duration x memory of every scrape and build invocation in the last N days, failures included.
Both need the header x-seer-token; only its SHA-256 is configured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import boto3

SCRAPE_FUNCTION = os.environ["SCRAPE_FUNCTION"]
EDITIONS = [e for e in os.environ.get("EDITIONS", "").split(",") if e]
LOG_GROUPS = {"scrape": os.environ["SCRAPE_LOG_GROUP"], "build": os.environ["BUILD_LOG_GROUP"]}
TOKEN_SHA256 = os.environ["TOKEN_SHA256"].strip().lower()
COOLDOWN_S = int(os.environ.get("COOLDOWN_SECONDS", "900"))
MAX_STARTS_PER_DAY = int(os.environ.get("MAX_STARTS_PER_DAY", "24"))  # scrape invocations; one sync is one
PRICE_GB_S = float(os.environ.get("LAMBDA_GB_S", "0.0000166667"))  # same list price as site.yaml admin.pricing
PRICE_REQUEST = float(os.environ.get("LAMBDA_PER_MILLION", "0.20")) / 1e6
MAX_DAYS = 30
MAX_ROWS = 200

# Platform lines plus the two lines that name the edition and run of an invocation.
PATTERN = '?REPORT ?"START RequestId" ?"[ERROR]" ?"TOTAL:" ?"build 20"'
START_RE = re.compile(r"START RequestId: (\S+)")
REPORT_RE = re.compile(
    r"REPORT RequestId: (\S+)\s+Duration: ([\d.]+) ms\s+Billed Duration: (\d+) ms\s+Memory Size: (\d+) MB"
    r"\s+Max Memory Used: (\d+) MB(?:\s+Init Duration: ([\d.]+) ms)?(?:\s+Status: (\w+))?"
)
TOTAL_RE = re.compile(r"TOTAL: edition=(\w+)")
BUILD_RE = re.compile(r"\bbuild (\d{8}T\d{6}Z-(\w+)): ")

lam = boto3.client("lambda")
logs = boto3.client("logs")
_last_sync = 0.0  # warm-container guard for clicks that land before the log line of the first one does


def reply(code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body),
    }


def authorized(token: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), TOKEN_SHA256)


def iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds")


def log_events(group: str, start_ms: int, end_ms: int, pattern: str, budget_s: float = 20) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"logGroupName": group, "startTime": start_ms, "endTime": end_ms, "filterPattern": pattern}
    out: list[dict[str, Any]] = []
    deadline = time.monotonic() + budget_s
    while True:
        try:
            page = logs.filter_log_events(**kwargs)
        except logs.exceptions.ResourceNotFoundException:
            return out
        out.extend(page.get("events", []))
        token = page.get("nextToken")
        if not token or time.monotonic() > deadline:
            return out
        kwargs["nextToken"] = token


def parse(fn: str, events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[int]]:
    """Invocations with a REPORT line (billed ones) and the start times of all invocations.

    One execution environment runs one invocation at a time, so per log stream the lines between a START and its
    REPORT belong to that invocation.
    """
    out: list[dict[str, Any]] = []
    starts: list[int] = []
    cur: dict[str, Any] | None = None
    for ev in sorted(events, key=lambda e: (e.get("logStreamName", ""), e["timestamp"])):
        msg, ts = ev["message"], ev["timestamp"]
        if (m := START_RE.match(msg)) and msg.startswith("START"):
            cur = {"fn": fn, "request_id": m.group(1), "start_ms": ts, "editions": [], "run_ids": [], "error": None}
            starts.append(ts)
        elif (m := REPORT_RE.match(msg)) and msg.startswith("REPORT"):
            rid, dur, billed, mem, used, init, status = m.groups()
            inv = (
                cur
                if cur and cur["request_id"] == rid
                else {
                    "fn": fn,
                    "request_id": rid,
                    "start_ms": ts - int(float(dur)),
                    "editions": [],
                    "run_ids": [],
                    "error": None,
                }
            )
            billed_ms, mem_mb = int(billed), int(mem)
            failed = bool(inv["error"]) or status in ("error", "failure", "timeout")
            inv.update(
                duration_ms=float(dur),
                billed_ms=billed_ms,
                memory_mb=mem_mb,
                max_memory_mb=int(used),
                init_ms=float(init) if init else 0.0,
                status="timeout" if status == "timeout" else "error" if failed else "ok",
                usd=billed_ms / 1000 * mem_mb / 1024 * PRICE_GB_S + PRICE_REQUEST,
            )
            out.append(inv)
            cur = None
        elif cur is not None:
            if msg.startswith("[ERROR] "):  # unhandled exception; logger errors are "[ERROR]<tab>time<tab>id<tab>text"
                cur["error"] = msg.splitlines()[0][:200]
            elif m := BUILD_RE.search(msg):
                cur["run_ids"].append(m.group(1))
                if m.group(2) not in cur["editions"]:
                    cur["editions"].append(m.group(2))
            elif m := TOTAL_RE.search(msg):
                if m.group(1) not in cur["editions"]:
                    cur["editions"].append(m.group(1))
    return out, starts


def cost(days: int) -> dict[str, Any]:
    now = time.time()
    start_ms, end_ms = int((now - days * 86400) * 1000), int(now * 1000)
    rows: list[dict[str, Any]] = []
    starts: dict[str, list[int]] = {}
    for fn, group in LOG_GROUPS.items():
        parsed, starts[fn] = parse(fn, log_events(group, start_ms, end_ms, PATTERN))
        rows += parsed
    rows.sort(key=lambda r: r["start_ms"], reverse=True)
    by_fn: dict[str, dict[str, Any]] = {}
    by_day: dict[str, float] = {}
    failed_usd = 0.0
    for r in rows:
        f = by_fn.setdefault(r["fn"], {"invocations": 0, "failed": 0, "billed_s": 0.0, "usd": 0.0})
        f["invocations"] += 1
        f["billed_s"] += r["billed_ms"] / 1000
        f["usd"] += r["usd"]
        if r["status"] != "ok":
            f["failed"] += 1
            failed_usd += r["usd"]
        day = iso(r["start_ms"])[:10]
        by_day[day] = by_day.get(day, 0.0) + r["usd"]
    for r in rows:
        r["start"] = iso(r.pop("start_ms"))
    day_starts = [t for t in starts.get("scrape", []) if t >= (now - 86400) * 1000]
    return {
        "generated": iso(now * 1000),
        "days": days,
        "prices": {"gb_s": PRICE_GB_S, "request": PRICE_REQUEST},
        "total_usd": sum(r["usd"] for r in rows),
        "failed_usd": failed_usd,
        "by_function": by_fn,
        "by_day": dict(sorted(by_day.items())),
        "sync": {
            "cooldown_s": COOLDOWN_S,
            "last_scrape_start": iso(max(starts.get("scrape") or [0])) if starts.get("scrape") else None,
            "scrape_starts_24h": len(day_starts),
            "max_per_day": MAX_STARTS_PER_DAY,
        },
        "invocations": rows[:MAX_ROWS],
    }


def sync() -> dict[str, Any]:
    global _last_sync
    now = time.time()
    recent = log_events(LOG_GROUPS["scrape"], int((now - 86400) * 1000), int(now * 1000), '"START RequestId"')
    times = [e["timestamp"] / 1000 for e in recent]
    if len(times) >= MAX_STARTS_PER_DAY:
        return reply(429, {"error": "daily_limit", "message": f"{len(times)} scrape starts in the last 24 h"})
    wait = COOLDOWN_S - (now - max(times + [_last_sync]))
    if wait > 0:
        return reply(429, {"error": "cooldown", "retry_after_s": int(wait) + 1})
    lam.invoke(FunctionName=SCRAPE_FUNCTION, InvocationType="Event", Payload=json.dumps({"editions": EDITIONS}))
    _last_sync = now
    return reply(202, {"started": EDITIONS, "at": iso(now * 1000), "cooldown_s": COOLDOWN_S})


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", ""), event.get("rawPath", "")
    if not authorized((event.get("headers") or {}).get("x-seer-token", "")):
        return reply(401, {"error": "unauthorized"})
    if method == "POST" and path.endswith("/sync"):
        return sync()
    if method == "GET" and path.endswith("/cost"):
        try:
            days = min(MAX_DAYS, max(1, int((event.get("queryStringParameters") or {}).get("days", "7"))))
        except ValueError:
            return reply(400, {"error": "days must be a number"})
        return reply(200, cost(days))
    return reply(404, {"error": "not_found"})
