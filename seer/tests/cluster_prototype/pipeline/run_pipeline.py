#!/usr/bin/env python3
"""Local stand-in for Step Functions: scrape -> ingest per edition (parallel), then stories, then export."""

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

TIMEOUT_S = 960
STEPS = ("scrape", "ingest", "stories", "export")
URL_TMPL = "http://127.0.0.1:{port}/2015-03-31/functions/function/invocations"
URLS = {name: os.environ.get(f"FN_{name.upper()}_URL", URL_TMPL.format(port=9101 + i)) for i, name in enumerate(STEPS)}
# The emulator serves one invocation at a time (a concurrent one crashes it), so calls to a function are serialized.
LOCKS = {name: threading.Lock() for name in STEPS}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
OUT_DIR = Path(__file__).resolve().parent.parent / "out"


class StepError(Exception):
    pass


def invoke(fn: str, event: dict) -> dict:
    req = urllib.request.Request(URLS[fn], data=json.dumps(event).encode(), method="POST")
    try:
        with LOCKS[fn], OPENER.open(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode()
    except Exception as e:
        raise StepError(f"{type(e).__name__}: {e}") from e
    try:
        out = json.loads(body) if body.strip() else None
    except ValueError as e:
        raise StepError(f"non-JSON response: {body[:300]}") from e
    if isinstance(out, dict) and "errorType" in out:
        raise StepError(f"{out['errorType']}: {out.get('errorMessage', '')}")
    return out


def summary(fn: str, out: dict) -> str:
    if fn == "scrape":
        return f"records={out.get('records')} bytes_gz={out.get('bytes_gz')}"
    if fn == "ingest":
        keys = ("inserted", "updated", "changed", "refreshed", "failures")
        return " ".join(f"{k}={out.get(k)}" for k in keys)
    if fn == "stories":
        eds = out.get("editions", {})
        parts = " ".join(f"{e}:new={v.get('new')},joined={v.get('joined')}" for e, v in eds.items())
        return f"embedded={out.get('embedded')} {parts}"
    return f"pages={len(out.get('pages', []))}"


def step(fn: str, event: dict, edition: str | None, results: list) -> dict:
    t0 = time.monotonic()
    rec = {"function": fn, "edition": edition, "event": event}
    results.append(rec)
    try:
        out = invoke(fn, event)
        rec.update(ok=True, output=out, wall_s=round(time.monotonic() - t0, 2))
        line = f"ok    {fn:8} {edition or '-':4} {rec['wall_s']:7.1f}s  {summary(fn, out)}"
    except StepError as e:
        rec.update(ok=False, error=str(e), wall_s=round(time.monotonic() - t0, 2))
        line = f"FAIL  {fn:8} {edition or '-':4} {rec['wall_s']:7.1f}s  {e}"
    print(line, flush=True)
    if not rec["ok"]:
        raise StepError(f"{fn} {edition or ''}: {rec['error']}".strip())
    return rec["output"]


def edition_flow(edition: str, hours: int | None, steps: list, results: list) -> None:
    event = {"edition": edition}
    if hours:
        event["hours"] = hours
    out = step("scrape", event, edition, results)
    if "ingest" in steps:
        step("ingest", out, edition, results)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--editions", default="mk,fr", help="comma-separated editions (default mk,fr)")
    ap.add_argument("--steps", default=",".join(STEPS), help="subset of scrape,ingest,stories,export")
    ap.add_argument("--hours", type=int, help="scrape window override")
    args = ap.parse_args()
    editions = [e.strip() for e in args.editions.split(",") if e.strip()]
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    bad = [s for s in steps if s not in STEPS]
    if bad or not steps or not editions:
        ap.error(f"invalid --steps/--editions (steps must be from {','.join(STEPS)})")
    if "ingest" in steps and "scrape" not in steps:
        ap.error("ingest needs the scrape output; include scrape in --steps (e.g. --steps scrape,ingest)")

    results: list = []
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    error = None
    try:
        if "scrape" in steps:
            with ThreadPoolExecutor(max_workers=len(editions)) as pool:
                futures = [pool.submit(edition_flow, e, args.hours, steps, results) for e in editions]
                errs = [f.exception() for f in futures]
            errs = [e for e in errs if e]
            if errs:
                raise StepError("; ".join(str(e) for e in errs))
        for fn in ("stories", "export"):
            if fn in steps:
                step(fn, {"editions": editions}, None, results)
    except StepError as e:
        error = str(e)
    total = round(time.monotonic() - t0, 2)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"pipeline-{started:%Y%m%dT%H%M%SZ}.json"
    doc = {
        "started_at": started.isoformat(),
        "editions": editions,
        "steps": steps,
        "ok": error is None,
        "error": error,
        "wall_s": total,
        "results": results,
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"{'done' if error is None else 'FAILED'} in {total:.1f}s -> {path}")
    return 0 if error is None else 1


if __name__ == "__main__":
    sys.exit(main())
