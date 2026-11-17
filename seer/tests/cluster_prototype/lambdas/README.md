# Lambda pipeline: contract (no database)

Two AWS Lambda functions and S3, nothing else. Run locally as Lambda container images behind AWS's Runtime Interface Emulator (RIE), with [versitygw](https://github.com/versity/versitygw) as the S3 stand-in; every object is a plain file under `data/s3/`.

```
Scheduler (hourly 08:00–22:00, one schedule for all editions)
   └► scrape(editions) ─► per edition: S3 raw batch + runs/{edition}/{run_id}.json
                              └► then one invoke of build(manifest_keys), in AWS (BUILD_FUNCTION)
                                    reads state/{edition}/window.json.gz (last 48 h)
                                    parse → embed new → join stories → render
                                    writes site pages, window, scrape state, archive, build report,
                                    admin summary, reader counts
```

| Function | AWS placement | Reads | Writes |
| --- | --- | --- | --- |
| `scrape` | No VPC; internet | news sites, `state/{edition}.json.gz` | one raw object per edition per run, plus a manifest |
| `build` | No VPC; internet for thumbnails and logos; e5 baked into the image; reserved concurrency 1 | manifest, raw object, window, `sources.yaml`, `categories.yaml`, `site.yaml`, other editions' summaries, CloudFront logs | public site pages, thumbnails, outlet logos, lab pages, admin data, reader counts, `days.json`, window, edition summary, scrape state, archive, build report |

No database, no VPC, no Step Functions. In AWS this is deployed with OpenTofu (`seer/infra/tofu/`, see [infra/README.md](../infra/README.md)). Only one build runs at a time (reserved concurrency 1); the window is also written with an S3 conditional write as a guard.

## S3 layout

Raw bucket `RAW_BUCKET` (default `seer-raw`):

| Key | Format | Written by | Kept |
| --- | --- | --- | --- |
| `raw/{edition}/{YYYY}/{MM}/{DD}/{HH}/{run_id}.jsonl.gz` | gzipped JSON lines, one record per fetched item, `INTELLIGENT_TIERING` | scrape | 2 years |
| `runs/{edition}/{run_id}.json` | scrape manifest (see below); its creation triggers build | scrape | 2 years |
| `state/{edition}.json.gz` | scrape state: what's known and each source's last good run | build | overwritten |
| `state/{edition}/window.json.gz` | hot state: `lambdas/build/model.py` `Window.to_json()`, gzipped | build | overwritten |
| `state/{edition}/days.json` | day index: `{"v", "edition", "updated_at", "days": [{"date", "stories", "lead_title", "lead_story", "lead_thumb", "top", "briefing"?}]}`, newest first, 3 years; `top` and `briefing` as in [build/SITE.md](build/SITE.md) | build | rolling |
| `state/{edition}/summary.json` | `{"edition", "name", "stories", "updated_at"}` for the landing page | build | overwritten |
| `state/logos.json` | outlet logo cache state: `{domain: {fetched_at, ok}}` | build | overwritten |
| `state/readers_cursor.json` | `{"done": [log file names counted but not yet deleted]}` | build | overwritten |
| `archive/{edition}/{YYYY}/{MM}/{DD}/{run_id}.jsonl.gz` | gzipped JSON lines: articles inserted or changed this run (full text, `kind: article`), stories created, changed or closed this run (`kind: story`, `state: open\|closed`) | build | 3 years |
| `builds/{edition}/{run_id}.json` | build report (the handler's output) | build | 2 years |
| `logs/cloudfront/…` | CloudFront standard logs (written by CloudFront, read and deleted by build; [build/READERS.md](build/READERS.md)) | CloudFront | deleted after counting; 7 days at most |

`run_id` = `{started:%Y%m%dT%H%M%SZ}-{edition}`. Key helpers: `common/seer_common/store.py` and `build/model.py`.

**Raw record** (one JSON object per line; `v` = 1):

```json
{"v": 1, "kind": "wp_post", "edition": "mk", "source": "nezavisen.mk", "fetched_at": "2026-11-15T10:00:03+00:00",
 "url": "<canonical url>", "loc": "<url fetched>", "status": 200,
 "payload": {"...": "the WordPress post JSON exactly as returned"},
 "meta": {"categories": {"12": "Македонија"}}}

{"v": 1, "kind": "html", "edition": "fr", "source": "lefigaro.fr", "fetched_at": "...",
 "url": "<canonical url>", "loc": "<url fetched>", "status": 200, "html": "<!doctype html>...",
 "meta": {"title": "<sitemap title>", "published": "<iso>", "image": "<sitemap image or null>",
          "lastmod": "<iso or null>", "refresh": false}}
```

A failed fetch keeps the record with `status` (0 for a network error), `"error": "<short reason>"` and no `html` or `payload`. A bot-challenge page counts as failed, `"error": "bot challenge"`.

**Manifest** (`runs/{edition}/{run_id}.json`): `run_id`, `edition`, `started_at`, `finished_at`, `raw_key`, `records`, `bytes_raw`, `bytes_gz`, `truncated`, `sources` (per domain: `method`, `listed`, `fetched`, `refresh`, `failures`, `errors`, `skipped`). Written once, by scrape.

**Scrape state** (`state/{edition}.json.gz`), written by build after every run; scrape reads it to decide what to fetch:

```json
{"v": 1, "edition": "fr", "generated_at": "<iso>", "last_run_id": "...", "last_run_started_at": "<iso>",
 "sources": {"lefigaro.fr": {"last_ok_started_at": "<iso>",
             "known": {"<canonical url>": {"p": "<published iso>", "c": "<checked iso or null>", "b": true}}}}}
```

`last_ok_started_at` is per source (`Window.source_last_ok`): build sets it to the run's `started_at` when that source has no errors and wasn't skipped in the manifest and the run wasn't `truncated`; otherwise it keeps the previous value. `known` holds the window's articles of that source published in the last `STATE_HOURS` (48); `b` is whether a body is stored.

Site bucket `SITE_BUCKET` (default `seer-site`): the public site (pages, `assets/`, `thumbs/`, `logos/`, feeds, `robots.txt`, `system/p.gif`; keys, caching and behaviour in [build/SITE.md](build/SITE.md)), the back-office page and its data under `system/admin/` (public in the prototype; `system/admin/data/` holds run summaries and reader counts, see SITE.md and READERS.md) and the analysis pages under `lab/` (`lab/index.html`, `lab/{edition}/index.html` Top, `lab/{edition}/latest.html` Latest; `noindex`, `text/html`, `max-age={SITE_CACHE_SECONDS}`). Relative links only, so the folder also works opened from disk.

## Events

Each handler is `handler.handler(event, context)` and returns a JSON-serializable dict; on failure it raises.

| Function | Input | Output |
| --- | --- | --- |
| `scrape` | `{"edition": "mk", "hours": 48?}` or `{"editions": ["mk", "fr"], "hours": 48?}` (editions in a row; with `BUILD_FUNCTION` set it then starts one build for all manifests written) | `{"edition", "run_id", "started_at", "raw_key", "manifest_key", "records", "bytes_raw", "bytes_gz", "truncated", "sources", "duration_s"}` |
| `build` | `{"manifest_keys": ["runs/...", ...]}` (several manifests in one invocation, so the model loads once; the rest goes to a new invocation when little time is left, `NEXT_BUILD_MIN_S`, default 300), an S3 event (`{"Records": [{"s3": {"bucket": {"name"}, "object": {"key": "runs/{edition}/{run_id}.json"}}}]}`, key URL-encoded) or `{"manifest_key": "runs/..."}` | `{"edition", "run_id", "skipped"?, "inserted", "updated", "changed", "refreshed", "failures", "embedded", "embed_s", "stories": {"unassigned", "joined", "new", "updated", "closed", "open", "multi_source"}, "thumbs": {"fetched", "reused", "failed", "skipped"}, "days": {"entries", "bytes"}, "site_pages": {"count", "skipped", "bytes"}, "readers": {"files", "lines", "pings", "html", "bots", "bad", "deleted", "catalog", "days"?, "unreadable"?, "catalog_error"?, "error"?}, "pages": [{"key", "bytes", "bytes_gz", "stories"}], "window_bytes", "archive_bytes", "pruned", "timings": {"load", "ingest", "embed", "assign", "thumbs", "logos", "days", "render", "readers", "save"}, "duration_s"}` |

`build` skips a manifest whose `started_at` is not newer than `Window.last_run_started_at` (already applied, or out of order) and returns `{"edition", "run_id", "skipped": "<reason>"}`.

## Build, step by step

1. Read the manifest; load the window (or start an empty one); remember its ETag.
2. **Ingest** the raw batch, streamed line by line: WordPress mapping, trafilatura extraction, images, canonical URLs, categories; meaningful-change detection (title changed, or difflib ratio on the first 5,000 chars below `1 − CHANGE_MIN_RATIO`); title-only article for a failed new fetch; a failed or empty refresh only sets `checked_at` (never moves it back). Same semantics as the SQL upsert it replaces. Idempotent.
3. Update `source_last_ok` from the manifest.
4. **Embed** articles with no vector (title + first 1,200 chars, `query: ` prefix, normalized). Edited articles keep their first vector.
5. **Assign** stories, ported from `clusterer/cluster.py` `run_stories`: close open stories whose `last_published` is older than `STORY_OPEN_HOURS`; place unassigned articles (published within `WINDOW_HOURS`, oldest first) into the open story with the highest average similarity to its members if ≥ `STORY_THRESHOLD`, within `STORY_MAX_GAP_HOURS` of its newest and `STORY_MAX_SPAN_HOURS` of its first article; otherwise start a new story. Refresh label, size, sources, published range, region/subject votes; a member's `content_changed_at` after the story's `updated_at` sets `updated_at` (the bump); `last_activity_at = max(last_published, updated_at)`; score = ln(1 + sources) × 2^(−hours since last activity / 6).
6. **Prune**: drop closed stories from the window, and articles older than `WINDOW_HOURS` that aren't members of an open story.
7. **Site**: `web.render.selection` → `thumbs.ensure` (≤ `THUMBS_PER_RUN` downloads; a failed image never fails the build) → `logos.ensure` (network only for outlets due; never raises) → `days.update` → `render_assets`, `render_edition`, `render_root`; plus the `lab/` pages (at most `TOP_LIMIT` / `LATEST_LIMIT` stories with ≥ `MIN_SOURCES` sources, viewer templates); every page is uploaded with its content type and cache header (existing `assets/` keys are skipped). Then `readers.process`: counts new CloudFront log files, writes the day files and the story catalog under `system/admin/data/readers/`, deletes the counted logs; never raises.
8. **Write** summary, archive, window (conditional: `IfMatch` the loaded ETag, or `IfNoneMatch: *` when new), `days.json`, scrape state, build report. Last, the admin run summary (`admin.summary` / `record` / `publish_static`); a failure there is logged and never fails the build.

## Module ownership

| File | Holds |
| --- | --- |
| `build/model.py` | `Article`, `Story`, `Window`, (de)serialization, keys. Fixed. |
| `build/ingest.py` | `apply_batch(window, records, ratio, now, full_bodies=None, domains=None) -> (counts: dict[str, int], touched: set[str])`; parsing helpers |
| `build/state.py` | `load_window(edition) -> (Window, etag or None)`, `save_window(window, etag) -> int`, `update_last_ok(window, manifest)`, `write_scrape_state(window, now) -> int`, `prune(window, now) -> list[Article]` |
| `build/archive.py` | `write_archive(edition, run_id, started, articles, stories, full_bodies=None, closed_ids=None) -> (key, bytes)` |
| `build/stories.py` | `embed_new(window) -> (count, seconds)`, `assign(window, categories, now) -> (counts, touched_story_ids, closed_stories)` |
| `build/render.py` | Lab pages: `render_edition(window, now) -> dict[key, html]` (keys under `lab/`), `edition_summary(window, now) -> dict`, `render_index(summaries, now) -> str`, `upload(pages) -> list[dict]` |
| `build/web/` | Public site: `selection`, `day_stories`, `render_edition`, `render_root`, `render_assets` (see SITE.md) |
| `build/thumbs.py`, `build/logos.py`, `build/days.py` | `thumbs.ensure(window, story_ids, now) -> counts`; `logos.ensure(sources, now) -> {domain: key or None}`; `days.update(window, cfg, now, previous) -> list[dict]`, `days.load/save` |
| `build/admin.py`, `build/readers.py` | Back-office run summaries and static admin page; reader counts from CloudFront logs (see SITE.md, READERS.md) |
| `build/handler.py` | Orchestration (steps 1–8) |
| `clusterer/categories.py` | `CategoryMap` and `vote`, shared by `build` and the legacy batch clusterer |

## Environment

| Variable | Functions | Default |
| --- | --- | --- |
| `RAW_BUCKET`, `SITE_BUCKET` | both | `seer-raw`, `seer-site` |
| `S3_ENDPOINT_URL`, `S3_AUTO_CREATE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | both | local only: `http://s3:7070` (or `http://127.0.0.1:7070` on the host network), `true`, `seer`, `seersecret`, `eu-central-1` |
| `SOURCES_FILE` | both | `/var/task/sources.yaml` |
| `HOURS`, `REQUEST_DELAY_S`, `MAX_ARTICLES_PER_SOURCE`, `REFRESH_HOURS`, `MAX_REFRESH_PER_SOURCE`, `RECHECK_MINUTES`, `IGNORE_ROBOTS` | scrape | `48`, `2`, `150`, `6`, `20`, `60`, `false` (`true` in Compose, experiments only) |
| `CHANGE_MIN_RATIO`, `STATE_HOURS`, `WINDOW_HOURS` | build | `0.05`, `48`, `48` |
| `MODEL`, `MODEL_PATH`, `STORY_THRESHOLD`, `STORY_OPEN_HOURS`, `STORY_MAX_GAP_HOURS`, `STORY_MAX_SPAN_HOURS`, `CATEGORIES_FILE` | build | `intfloat/multilingual-e5-base`, `/opt/model/e5-base`, `0.92`, `48`, `18`, `24`, `/var/task/categories.yaml` |
| `SITE_CACHE_SECONDS`, `TOP_LIMIT`, `LATEST_LIMIT`, `MIN_SOURCES`, `TEMPLATES_DIR` | build (lab pages only; the public site uses `cache_seconds` and `limits` in `site.yaml`) | `300`, `60`, `60`, `2`, `/var/task/templates` |
| `SITE_FILE`, `THUMBS_PER_RUN` | build | `/var/task/site.yaml`, `80` |
| `LOGS_DIR`, `LOGS_BUCKET`, `LOGS_PREFIX` | build (reader statistics) | unset (local: `/logs`), `RAW_BUCKET`, `logs/cloudfront/` |
| `BATCH_SIZE` | build (embedding batch) | `32` (`8` in the AWS stack: same vectors, less memory) |
| `RAW_STORAGE_CLASS` | scrape | `INTELLIGENT_TIERING` |

## Local run

| Service | Image | Network | Invoke URL (host) |
| --- | --- | --- | --- |
| `s3` | `versity/versitygw:v1.11.0`, `posix /data`, `./data/s3:/data` | default; port 7070 | — |
| `fn-scrape` | `lambdas/scrape/Dockerfile` | default, or host network behind the proxy (RIE on `0.0.0.0:9101`) | `http://127.0.0.1:9101/2015-03-31/functions/function/invocations` |
| `fn-build` | `lambdas/build/Dockerfile` | default, or host network behind the proxy (RIE on `0.0.0.0:9102`, runtime API on `127.0.0.1:9003`); needs internet for thumbnails and logos; mounts `./data/logs` at `/logs` | `http://127.0.0.1:9102/2015-03-31/functions/function/invocations` |

`pipeline/run_pipeline.py` (standard library only) stands in for the scheduler and the build trigger: scrape per edition, then build with an S3-event-shaped payload for the new manifest (the AWS stack has no S3 event: scrape starts the build). `--replay EDITION` deletes the edition's window, summary and scrape state (`days.json`, logos and reader counts stay), then applies every manifest under `data/s3/seer-raw/runs/{edition}/` in order.

**Images** build from `public.ecr.aws/lambda/python:3.12` with the build context `tests/cluster_prototype/`. Behind the proxy, append `certs/*.crt` to `/etc/pki/tls/certs/ca-bundle.crt` and set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` to it. Copy `lambdas/common/seer_common/` to `/var/task/seer_common/`. Use the base image's boto3; pin everything else exactly. Lambda can write only to `/tmp`; local containers run with `read_only: true` and a `/tmp` tmpfs.

**Legacy (Postgres) stack**, Compose profile `legacy`: `db`, `viewer` and the batch `clusterer` (`make cluster`), kept for threshold experiments and for comparing results while the database-free pipeline proves itself.
