# Lambda split: contract

The hourly pipeline as four AWS Lambda functions, run locally as Lambda container images behind AWS's Runtime Interface Emulator (RIE). A local S3 stand-in, [versitygw](https://github.com/versity/versitygw), keeps every object as a plain file under `data/s3/`.

```
Scheduler ─► Step Functions (one run per hour, 08:00–22:00)
   Map over editions:  scrape ─► S3 raw ─► ingest ─► Postgres
   then:               stories (embed new + join stories) ─► export (static HTML ─► S3 site)
```

| Function | AWS placement | Reads | Writes |
| --- | --- | --- | --- |
| `scrape` | Outside the VPC; internet for free | news sites, `state/{edition}.json.gz` | one raw object per edition per run, plus a manifest |
| `ingest` | VPC, no internet | raw object, `sources.yaml` | `articles`, `sources`; updated manifest; `state/{edition}.json.gz` |
| `stories` | VPC, no internet; model in the image | `articles`, `embeddings`, `stories` | `embeddings`, `stories`, `story_articles` |
| `export` | VPC, no internet | `stories`, `articles` | static pages in the site bucket |

VPC functions reach S3 through a gateway endpoint (free) and Postgres directly. Nothing needs a NAT gateway.

## S3 layout

Raw bucket `RAW_BUCKET` (default `seer-raw`):

| Key | Format | Written by |
| --- | --- | --- |
| `raw/{edition}/{YYYY}/{MM}/{DD}/{HH}/{run_id}.jsonl.gz` | gzipped JSON lines, one record per fetched item, storage class `INTELLIGENT_TIERING` | scrape |
| `runs/{edition}/{run_id}.json` | JSON manifest: `run_id`, `edition`, `started_at`, `finished_at`, `raw_key`, `records`, `bytes_raw`, `bytes_gz`, `sources` (per domain: `method`, `listed`, `fetched`, `refresh`, `failures`, `errors`, `skipped`); ingest adds an `ingest` object | scrape, then ingest |
| `state/{edition}.json.gz` | gzipped JSON, see below | ingest |

`run_id` = `{started:%Y%m%dT%H%M%SZ}-{edition}`. Key helpers are in `common/seer_common/store.py`.

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

**State** (`state/{edition}.json.gz`), rebuilt from Postgres by ingest after every run; scrape reads it to decide what to fetch:

```json
{"v": 1, "edition": "fr", "generated_at": "<iso>", "last_run_id": "...", "last_run_started_at": "<iso>",
 "sources": {"lefigaro.fr": {"last_ok_started_at": "<iso>",
             "known": {"<canonical url>": {"p": "<published iso>", "c": "<checked iso or null>", "b": true}}}}}
```

`last_ok_started_at` is per source: ingest sets it to the run's `started_at` when that source has no errors and wasn't skipped in the run's manifest (and the run wasn't `truncated`), otherwise it carries the previous value forward. A source that never succeeded has none.

`known` holds the source's articles published in the last `STATE_HOURS` (48); `b` is whether a body is stored.

Site bucket `SITE_BUCKET` (default `seer-site`): `index.html`, `{edition}/index.html` (Top), `{edition}/latest.html` (Latest). Uploaded with `ContentType: text/html; charset=utf-8` and `CacheControl: public, max-age={SITE_CACHE_SECONDS}`. Links between pages are relative, so the folder also works opened from disk.

## Events

Each handler is `handler.handler(event, context)` and returns a JSON-serializable dict; on failure it raises.

| Function | Input | Output |
| --- | --- | --- |
| `scrape` | `{"edition": "mk", "hours": 48?}` (`hours` overrides `HOURS`, for backfills) | `{"edition", "run_id", "started_at", "raw_key", "manifest_key", "records", "bytes_raw", "bytes_gz", "sources", "duration_s"}` |
| `ingest` | the scrape output (uses `edition`, `run_id`, `raw_key`, `manifest_key`, `started_at`) | `{"edition", "run_id", "inserted", "updated", "changed", "refreshed", "failures", "state_key", "duration_s"}` |
| `stories` | `{"editions": ["mk", "fr"]?}` (omitted = every edition in `sources`) | `{"embedded", "embed_s", "editions": {"mk": {"unassigned", "joined", "new", "updated", "closed", "open", "multi_source"}}, "duration_s"}` |
| `export` | `{"editions": ["mk", "fr"]?}` | `{"pages": [{"key", "bytes", "bytes_gz", "stories"}], "duration_s"}` |

## Behaviour rules

- **scrape fetches only; it never touches Postgres.** `wp_api`: when state has the source's `last_ok_started_at`, request posts with `after = now − HOURS` and `modified_after = last_ok_started_at − 10 min` (new and edited posts only); without state, or if the site rejects `modified_after` (HTTP 400), use `after` alone. `news_sitemap`: fetch window entries (`HOURS`, newest first, capped at `MAX_ARTICLES_PER_SOURCE`) that aren't in `known` with `b: true`; then re-fetch up to `MAX_REFRESH_PER_SOURCE` known entries with a body, published within `REFRESH_HOURS` and not checked in the last `RECHECK_MINUTES`, newest first, with `meta.refresh: true`. Rate limit (1 request per `REQUEST_DELAY_S` per host), retries, the honest user agent, robots handling and per-source isolation are kept from the original single-process scraper. One raw object per edition per run, even if empty.
- **ingest does all parsing:** WordPress mapping, trafilatura extraction, images, canonical URLs, categories, meaningful-change detection (`CHANGE_MIN_RATIO`), and the title-only row for failed new fetches. A failed or empty refresh only sets `checked_at`. It's idempotent: ingesting the same raw object twice changes nothing the second time.
- **Embed once.** `stories` embeds only articles with no embedding for `MODEL`. An edited article keeps its first embedding and is never re-clustered; its `content_changed_at` still bumps its story's activity and score. SQL must not require `embeddings.content_hash = articles.content_hash`.
- **The stories model is baked into the image** at `MODEL_PATH` and loaded offline (`HF_HUB_OFFLINE=1`). Embedding keys still use `MODEL`.
- **Read-only filesystem.** Lambda can write only to `/tmp`; local containers run with `read_only: true` and a `/tmp` tmpfs to catch violations.

## Environment

| Variable | Functions | Default |
| --- | --- | --- |
| `RAW_BUCKET`, `SITE_BUCKET` | all | `seer-raw`, `seer-site` |
| `S3_ENDPOINT_URL`, `S3_AUTO_CREATE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | all | local only: `http://s3:7070` (or `http://127.0.0.1:7070` on the host network), `true`, `seer`, `seersecret`, `eu-central-1` |
| `DATABASE_URL` | ingest, stories, export | `postgresql://seer:seer@db:5432/seer` |
| `SOURCES_FILE` | scrape, ingest | `/var/task/sources.yaml` |
| `HOURS`, `REQUEST_DELAY_S`, `MAX_ARTICLES_PER_SOURCE`, `REFRESH_HOURS`, `MAX_REFRESH_PER_SOURCE`, `RECHECK_MINUTES`, `IGNORE_ROBOTS` | scrape | `48`, `2`, `150`, `6`, `20`, `60`, `false` (`true` in Compose, experiments only) |
| `CHANGE_MIN_RATIO`, `STATE_HOURS` | ingest | `0.05`, `48` |
| `MODEL`, `MODEL_PATH`, `WINDOW_HOURS`, `STORY_*`, `CATEGORIES_FILE` | stories | `intfloat/multilingual-e5-base`, `/opt/model/e5-base`, `48`, as in Compose, `/var/task/categories.yaml` |
| `SITE_CACHE_SECONDS`, `TOP_LIMIT`, `LATEST_LIMIT` | export | `300`, `60`, `60` |

## Local run

| Service | Image | Network | Invoke URL (host) |
| --- | --- | --- | --- |
| `s3` | `versity/versitygw:v1.11.0`, `posix /data`, `./data/s3:/data` | default; port 7070 | — |
| `fn-scrape` | `lambdas/scrape/Dockerfile` | default, or host network behind the proxy (RIE on `0.0.0.0:9101`) | `http://127.0.0.1:9101/2015-03-31/functions/function/invocations` |
| `fn-ingest` | `lambdas/ingest/Dockerfile` | default only (no internet) | port 9102 |
| `fn-stories` | `lambdas/stories/Dockerfile` | default only (no internet) | port 9103 |
| `fn-export` | `lambdas/export/Dockerfile` | default only (no internet) | port 9104 |

`pipeline/run_pipeline.py` (standard library only) stands in for Step Functions: scrape → ingest per edition (editions in parallel), then stories, then export. `infra/state_machine.asl.json` is the same flow for AWS.

**Images** build from `public.ecr.aws/lambda/python:3.12` with the build context `tests/cluster_prototype/`. Behind the proxy, append `certs/*.crt` to `/etc/pki/tls/certs/ca-bundle.crt` and set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` to it, as the existing Dockerfiles do for Debian. Copy `lambdas/common/seer_common/` to `/var/task/seer_common/`. Use the base image's boto3; pin everything else exactly.
