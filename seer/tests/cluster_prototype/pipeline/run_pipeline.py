#!/usr/bin/env python3
"""Local stand-in for the scheduler and the S3 event: scrape per edition, then build from the new manifest."""

import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

TIMEOUT_S = 960
STEPS = ("scrape", "build")
URL_TMPL = "http://127.0.0.1:{port}/2015-03-31/functions/function/invocations"
URLS = {name: os.environ.get(f"FN_{name.upper()}_URL", URL_TMPL.format(port=9101 + i)) for i, name in enumerate(STEPS)}
# The emulator serves one invocation at a time (a concurrent one crashes it), so calls to a function are serialized.
LOCKS = {name: threading.Lock() for name in STEPS}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(os.environ.get("OUT_DIR") or ROOT / "out")
RAW_BUCKET = os.environ.get("RAW_BUCKET", "seer-raw")


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


def s3_event(manifest_key: str) -> dict:
    return {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": RAW_BUCKET},
                    "object": {"key": urllib.parse.quote_plus(manifest_key, safe="/")},
                },
            }
        ]
    }


def summary(fn: str, out: dict) -> str:
    if fn == "scrape":
        return f"records={out.get('records')} bytes_gz={out.get('bytes_gz')}"
    if out.get("skipped"):
        return f"skipped={out['skipped']}"
    st = out.get("stories") or {}
    keys = ("joined", "new", "open", "multi_source")
    parts = " ".join(f"{k}={st.get(k)}" for k in keys)
    head = f"inserted={out.get('inserted')} changed={out.get('changed')} embedded={out.get('embedded')}"
    return f"{head} {parts} duration_s={out.get('duration_s')}"


def step(fn: str, event: dict, edition: str | None, results: list, label: str = "") -> dict:
    t0 = time.monotonic()
    rec = {"function": fn, "edition": edition, "event": event}
    results.append(rec)
    try:
        out = invoke(fn, event)
        rec.update(ok=True, output=out, wall_s=round(time.monotonic() - t0, 2))
        line = f"ok    {fn:8} {edition or '-':4} {rec['wall_s']:7.1f}s  {label}{summary(fn, out)}"
    except StepError as e:
        rec.update(ok=False, error=str(e), wall_s=round(time.monotonic() - t0, 2))
        line = f"FAIL  {fn:8} {edition or '-':4} {rec['wall_s']:7.1f}s  {label}{e}"
    print(line, flush=True)
    if not rec["ok"]:
        raise StepError(f"{fn} {edition or ''}: {rec['error']}".strip())
    return rec["output"]


def manifests(raw_dir: Path, edition: str) -> list[str]:
    """Manifest keys of an edition, oldest first (run ids start with a UTC timestamp)."""
    return [f"runs/{edition}/{p.name}" for p in sorted((raw_dir / "runs" / edition).glob("*.json"))]


def edition_flow(edition: str, hours: int | None, steps: list, raw_dir: Path, results: list) -> None:
    if "scrape" in steps:
        event = {"edition": edition}
        if hours:
            event["hours"] = hours
        out = step("scrape", event, edition, results)
        key = out.get("manifest_key")
        if not key:
            raise StepError(f"scrape {edition}: output has no manifest_key")
    else:
        found = manifests(raw_dir, edition)
        if not found:
            raise StepError(f"build {edition}: no manifests in {raw_dir / 'runs' / edition}")
        key = found[-1]
    if "build" in steps:
        step("build", s3_event(key), edition, results, label=f"{key.rsplit('/', 1)[-1]} ")


def replay(editions: list, raw_dir: Path, results: list) -> None:
    for edition in editions:
        for rel in (f"state/{edition}/window.json.gz", f"state/{edition}/summary.json", f"state/{edition}.json.gz"):
            path = raw_dir / rel
            if path.is_file():
                path.unlink()
                print(f"delete {path}", flush=True)
            else:
                print(f"absent {path}", flush=True)
        for key in manifests(raw_dir, edition):
            step("build", s3_event(key), edition, results, label=f"{key.rsplit('/', 1)[-1]} ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--editions", default="mk,fr", help="comma-separated editions (default mk,fr)")
    ap.add_argument(
        "--steps", default=",".join(STEPS), help="subset of scrape,build; build alone uses the latest manifest"
    )
    ap.add_argument("--hours", type=int, help="scrape window override")
    ap.add_argument(
        "--replay",
        nargs="?",
        const="",
        metavar="EDITION[,EDITION]",
        help="delete the edition's state, then build every manifest in order (default: --editions)",
    )
    ap.add_argument("--s3-dir", default=os.environ.get("S3_DIR") or str(ROOT / "data" / "s3"), help="local S3 folder")
    args = ap.parse_args()
    editions = [e.strip() for e in (args.replay or args.editions).split(",") if e.strip()]
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    bad = [s for s in steps if s not in STEPS]
    if bad or not steps or not editions:
        ap.error(f"invalid --steps/--editions (steps must be from {','.join(STEPS)})")
    raw_dir = Path(args.s3_dir) / RAW_BUCKET

    results: list = []
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    error = None
    try:
        if args.replay is not None:
            steps = ["replay"]
            replay(editions, raw_dir, results)
        else:
            with ThreadPoolExecutor(max_workers=len(editions)) as pool:
                futures = [pool.submit(edition_flow, e, args.hours, steps, raw_dir, results) for e in editions]
                errs = [f.exception() for f in futures]
            errs = [e for e in errs if e]
            if errs:
                raise StepError("; ".join(str(e) for e in errs))
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
