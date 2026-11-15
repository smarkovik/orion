# Seer: guide for agents

## What Seer is

Seer is a news aggregator, inspired by [TIME.mk](https://time.mk) but built our own way. It collects articles from a list of news sites, groups articles about the same event into stories, ranks them, and shows them per edition. An edition is one language plus one market: today `mk` (Macedonian) and `fr` (French).

**Status:** research and prototypes. Nothing is in production.

**The plan has three stages:**

1. A scraper with a discovery plan per site that upserts articles.
2. Clustering and storage.
3. A website.

The plan doc is at https://claude.ai/artifact/R8G6t1iVaTFxkMmi7ZsgwQ.

**No LLM in the pipeline.** Scraping is rule-based. Embeddings come from a small local encoder (`intfloat/multilingual-e5-base`, CPU). Clustering is scikit-learn. Categories are static YAML rules.

## Layout

| Path | Holds |
| --- | --- |
| `docs/` | Research write-ups. Start with `cluster-prototype-findings.md` and `adding-sources-and-editions.md`. |
| `docs/sources.md`, `sources.csv` | The 113 Macedonian outlets from TIME.mk, with verified websites and RSS feeds |
| `tests/` | Prototypes behind the research. They aren't unit tests and CI doesn't run them. |
| `tests/cluster_prototype/` | The working end-to-end prototype, in Docker |
| `tests/scraper/` | Latest-news scraper for any site: RSS, then homepage links, then Lightpanda |
| `tests/sources/` | Resolver from outlet names to verified domains and feeds |
| `tests/tokenizers/` | Macedonian tokenizer comparison |
| `tests/postgres/` | Standalone Postgres + pgvector setup and smoke test |

## Cluster prototype (`tests/cluster_prototype/`)

The hourly pipeline runs as four AWS Lambda container images, invoked locally through AWS's Runtime Interface Emulator. The contract (S3 layout, events, env) is [`lambdas/README.md`](tests/cluster_prototype/lambdas/README.md); the AWS plan and cost are in the infrastructure doc (https://claude.ai/artifact/CDgvfxgsj3SiQJx4Zwsf66).

| Service | Does |
| --- | --- |
| `db` | Postgres 16 + pgvector 0.8.7; schema in `db/schema.sql` (idempotent, applied by `make migrate`) |
| `s3` | Local S3 stand-in ([versitygw](https://github.com/versity/versitygw)); every object is a plain file under `data/s3/` |
| `fn-scrape` | Lambda 1, outside the VPC. Fetches only new or edited items (per-source state in S3) and writes one gzipped JSONL raw batch per edition per run, plus a manifest. Never touches Postgres. |
| `fn-ingest` | Lambda 2, VPC, no internet. Parses the raw batch (WordPress mapping, trafilatura, images, categories), upserts articles, flags meaningful changes, rewrites the state file. Idempotent. |
| `fn-stories` | Lambda 3, VPC, no internet; e5 baked into the image. Embeds new articles only and adds them to stable stories. |
| `fn-export` | Lambda 4, VPC, no internet. Renders Top and Latest per edition to the site bucket as static HTML. |
| `clusterer` | Batch experiments only (`make cluster`): re-clusters the whole window at each threshold into `cluster_runs`. |
| `viewer` | FastAPI pages for inspection. `/stories` shows Top or Latest per edition; `/editions` shows stories in CSS tabs; `/runs/{id}` shows batch experiments. |

`pipeline/run_pipeline.py` stands in for Step Functions: scrape → ingest per edition, then stories, then export. `infra/` holds the Step Functions definition and the raw bucket's lifecycle and Intelligent-Tiering configs.

**How stories are built** (`MODE=stories`):

- An article joins the best open story only if its average similarity to the story's members is at least `STORY_THRESHOLD` (0.92). That's average linkage; comparing to the mean vector instead drifted into a 96-article mega-story.
- It must also be within `STORY_MAX_GAP_HOURS` (18) of the story's newest article and within `STORY_MAX_SPAN_HOURS` (24) of its first. The span cap is what splits daily weather forecasts.
- Otherwise the article starts a new story. Stories close after `STORY_OPEN_HOURS` (48) without new articles.
- Score = ln(1 + sources) × 2^(−hours since last activity / 6). Last activity is the newest article, or a member's meaningful text change.
- **Embed once.** An edited article keeps its first embedding and its story; the edit only bumps the story's activity, so it rises in Top. Nothing is re-embedded or re-clustered.

**Data model:**

- `sources.language` holds the edition code.
- `articles` carries `source_categories`, `image_url` and `source_modified_at`, plus `checked_at`, `content_changed_at` and `change_count` for updates. A change counts as meaningful if the title changed or more than 5% of the text did.
- `embeddings` hold one vector per article and model, written once.
- S3 raw bucket (`data/s3/seer-raw/` locally): `raw/` batches are the record (2-year expiry in AWS), `runs/` manifests, `state/` what scrape has already seen.
- `stories` and `story_articles` hold the live, stable stories; an article belongs to at most one story.
- `cluster_runs`, `clusters` and `cluster_articles` hold batch experiments, one run per edition and threshold.

**Run it:**

- `make` lists the targets.
- `make all` builds, starts, runs the whole pipeline and opens the viewer.
- `make refresh` runs scrape → ingest → stories → export; `make scrape`, `make stories` and `make site` run parts. `EDITION=fr` limits a run to one edition; `HOURS` widens scrape's window (backfills).
- `make raw` lists the raw batches, manifests and state with sizes. The static site is at `data/s3/seer-site/index.html`.
- `make cluster` runs a batch experiment and `make reset-stories` rebuilds stories from scratch.
- Each run's step outputs and timings land in `out/pipeline-<UTC>.json`.

**Knobs:**

- Make variables: `HOURS`, `EDITION`; for batch runs `THRESHOLDS`, `WINDOW_HOURS`, `MODEL`, `MAX_ARTICLES`, `RUN`, `THRESHOLD`, `VIEW`, `MIN_SOURCES`.
- Compose environment of the `fn-*` services: `STORY_*`, `REFRESH_HOURS`, `MAX_REFRESH_PER_SOURCE`, `RECHECK_MINUTES`, `CHANGE_MIN_RATIO`, `STATE_HOURS`, `TOP_LIMIT`, `LATEST_LIMIT`, `SITE_CACHE_SECONDS`.

## Conventions

- **Where things go.** Prototypes go in `tests/` and research write-ups in `docs/`. Seer doesn't depend on Orion's code or stack.
- **Python.** 3.12, type hints, black and flake8 at line length 120, exact pins in `requirements.txt`. Keep comments minimal: one short line, only when the code isn't obvious.
- **Contract first.** For multi-part changes, the schema, `sources.yaml`, `categories.yaml`, Compose env variables and Makefile targets are fixed first. Components are then written against them, in parallel if useful.
- **Exploration workflow.** Open a PR, build, test (`make build up`, run the affected targets, check the viewer), then merge. Don't wait on watchers. CI skips changes that only touch `seer/` (`paths-ignore` in `.github/workflows/ci.yml`), so lint locally.
- **Git.** Commits use the user's git identity, never the agent's. Attribution goes on the PR.

## Scraping rules

- **Honest user agent:** `SeerBot/0.1`. Rate limit: 1 request per 2 s per host.
- **robots.txt.** It's ignored only in experiments (`IGNORE_ROBOTS=true` in Compose). A product must obey it.
- **Never bypass bot protection** (Cloudflare, DataDome) and never scrape TIME.mk.
- **Store, don't republish.** Full text is kept internally, for clustering only.

## Findings that shape decisions

| Topic | Finding |
| --- | --- |
| Threshold | 0.92 cosine fits both mk and fr. e5 similarity scores sit in a high band: 0.82 merges 74% of articles into one cluster, and 0.94 starts splitting stories. |
| Volume | 48 h ≈ 1,160 mk and 1,190 fr articles. Embedding runs at 3.4–5.3 articles/s on CPU. |
| Stories (0.92) | mk: 194 stories with 2+ sources (largest 24). fr: 134 (largest 30). |
| Categories | mk sites file by place (region 84%, subject 49%). fr sites file by subject (region 40%, subject 81%). Each edition needs a fallback for its weak facet. |
| Stories (incremental) | Match the batch run: mk 194 and fr 141 stories with 2+ sources (batch: 193 and 134). The largest are 15 and 28 articles; the longest span is 23 h. A second run with no new articles changes nothing. |
| Images and updates | Featured images on 100% of recent mk articles; og:image or sitemap images on 56–100% of recent fr articles per site. Le Figaro's extraction varies between fetches, so it raises a few false "updated" flags. |
| Failure modes | Agency copy inflates source counts; all-caps titles; weak 1-vote categories. The daily weather merge is fixed by the 24 h span cap. |
| Discovery | 88 of 105 reachable MK sites expose the WordPress API. The French news sites tested publish news sitemaps covering 48 h. |

## Gotchas in cloud sandboxes

- **`dockerd` isn't running at the start of a session.** Every Docker-using `make` target starts it.
- **Containers reach the internet only through the HTTPS proxy.** `docker-compose.proxy.yml` adds host networking, proxy variables and the CA. `run.sh` and the Makefile use it when `HTTPS_PROXY` is set.
- **Compose v5 builds through bake,** which needs `--allow=network.host`. `make build` handles that.
- **Docker Hub can rate-limit base-image lookups (429).** Retry later or log in.
- **Only `fn-scrape` gets the proxy.** It runs on the host network with the emulator moved to port 9101; the other three Lambdas sit on the default network with no proxy, so they provably need no internet (like a VPC without NAT).
- **The Lambda emulator takes one call at a time** and crashes on concurrent calls to the same container. The runner serializes calls per function; real Lambda scales out. Two host-network emulators also clash on the runtime API port 9001.

## Open questions

- A subject and region fallback per edition: fixed vectors per category, or the edition's home region.
- A minimum vote for categories, for example 2 or more votes and at least 20% of a story's articles.
- Syndication fingerprints, so agency copy counts once.
- A more stable extraction or a text-normalization step, so Le Figaro stops raising false "updated" flags.
- Images. Linking to outlets' images is fine for the prototype but needs a legal check before going public, since agency photos are licensed.
- Linking stories that continue past the 24 h span into one longer topic thread.
- Linking the same story across editions. The US airspace story appears in both mk and fr today.
- Labelled pairs to measure precision and recall properly.
