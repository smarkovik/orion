# Seer: guide for agents

## What Seer is

Seer is a news aggregator, inspired by [TIME.mk](https://time.mk) but built our own way. It collects articles from a list of news sites, groups articles about the same event into stories, ranks them, and shows them per edition. An edition is one language plus one market: today `mk` (Macedonian) and `fr` (French).

**Status:** research and a working prototype. Staging runs in the sandbox AWS account and deploys from CI; production is set up but off until `SEER_DEPLOY_ENABLED` is `true`, so nothing is in production yet.

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
| `infra/tofu/` | OpenTofu for the AWS staging and production accounts (see its README) |
| `tests/` | Prototypes behind the research. They aren't unit tests and CI doesn't run them. |
| `tests/cluster_prototype/` | The working end-to-end prototype: two Lambda images and S3, run in Docker |
| `tests/scraper/` | Latest-news scraper for any site: RSS, then homepage links, then Lightpanda |
| `tests/sources/` | Resolver from outlet names to verified domains and feeds |
| `tests/tokenizers/` | Macedonian tokenizer comparison |
| `tests/postgres/` | Standalone Postgres + pgvector smoke test, unrelated to the prototype's storage |

## Cluster prototype (`tests/cluster_prototype/`)

The hourly pipeline is two AWS Lambda container images and S3, with no database. Locally they run behind AWS's Runtime Interface Emulator. The contract (S3 layout, events, env, module ownership) is [`lambdas/README.md`](tests/cluster_prototype/lambdas/README.md); the AWS plan and cost are in the infrastructure doc (https://claude.ai/artifact/CDgvfxgsj3SiQJx4Zwsf66).

| Service | Does |
| --- | --- |
| `s3` | Local S3 stand-in ([versitygw](https://github.com/versity/versitygw)); every object is a plain file under `data/s3/` |
| `fn-scrape` | Lambda 1. Fetches only new or edited items (per-source state in S3) and writes one gzipped JSONL raw batch per edition per run, plus a manifest. |
| `fn-build` | Lambda 2; e5 baked into the image. Triggered by the manifest (an S3 event in AWS). Loads the edition's hot window (last 48 h, about 5–7 MB with vectors), parses the batch, embeds new articles only, joins stories, fetches one thumbnail per shown story (the only internet it needs), renders the public site (`lambdas/build/web/`, settings and all interface text in `site.yaml`) and the analysis pages under `/lab/`, and writes the window, day index, scrape state, a 3-year archive file and a build report. |
| `db`, `viewer`, `clusterer` | **Legacy** (Compose profile `legacy`): the earlier Postgres version, kept for threshold experiments (`make cluster`) and for `make compare`. |

`pipeline/run_pipeline.py` stands in for the scheduler and the S3 event. `make replay` rebuilds an edition from scratch by applying every manifest in order; builds use the manifest's own clock, so a replay reproduces the live result. `infra/` holds the S3 event, schedule, lifecycle and Intelligent-Tiering configs.

**How stories are built** (`lambdas/build/stories.py`, ported from the Postgres `clusterer/cluster.py`):

- An article joins the best open story only if its average similarity to the story's members is at least `STORY_THRESHOLD` (0.92). That's average linkage; comparing to the mean vector instead drifted into a 96-article mega-story.
- It must also be within `STORY_MAX_GAP_HOURS` (18) of the story's newest article and within `STORY_MAX_SPAN_HOURS` (24) of its first. The span cap is what splits daily weather forecasts.
- Otherwise the article starts a new story. Stories close after `STORY_OPEN_HOURS` (48) without new articles.
- Score = ln(1 + sources) × 2^(−hours since last activity / 6). Last activity is the newest article, or a member's meaningful text change.
- **Embed once.** An edited article keeps its first embedding and its story; the edit only bumps the story's activity, so it rises in Top. Nothing is re-embedded or re-clustered.

**Data model** (no database):

- `lambdas/build/model.py`: `Article`, `Story` and `Window`, stored as `state/{edition}/window.json.gz` (articles of the last 48 h with their vectors, open stories). A change counts as meaningful if the title changed or more than 5% of the text did; each article keeps one vector, written once.
- `sources.yaml` editions are the unit: each edition has its own window, state, archive and pages, and builds run one at a time.
- S3 raw bucket (`data/s3/seer-raw/` locally): `raw/` batches are the record (2-year expiry in AWS), `runs/` manifests (their creation triggers build), `state/` scrape state and windows, `archive/` processed articles and stories (3 years), `builds/` build reports.

**Run it:**

- `make` lists the targets. `make build up` builds and starts S3 and the two Lambdas.
- `make refresh` scrapes both editions and builds them; `make scrape` only scrapes; `make site` rebuilds from the latest manifests. `EDITION=fr` limits a run to one edition; `HOURS` widens scrape's window (backfills).
- **Reader features** (all browser-only, no accounts): week pages, morning briefing, since-your-last-visit marks, follow a story, outlet logos, "developing" marker, share, text size and pictures-off, installable app with offline reading.
- **Admin** at `/system/admin/` (public in the prototype, `noindex`; access control comes later): a static page reading per-run JSON summaries from `system/admin/data/` (scrape, stories, sizes, timings, thumbnails, cost estimate); 14/30/90-day windows; kept 400 days. Its Readers tab shows reader statistics (contract: `lambdas/build/READERS.md`): pages send a small first-party ping with no ID or fingerprint, and build counts it from CloudFront logs, then deletes the logs. `make preview` writes logs in the same format locally.
- **Deploy:** OpenTofu in `seer/infra/tofu/` (staging and production accounts). Staging deploys on push to `main`; production deploys by a manual run on a ref (default: tip of `main`). The staging role ARN is in the workflow file; production is off until the repository variable `SEER_DEPLOY_ENABLED` is `true`.
- `make preview` serves the site at http://localhost:8090. Public pages: `index.html`, `{edition}/index.html`, sections `{edition}/s/`, story pages `{edition}/story/`, days `{edition}/YYYY/MM/DD.html`, calendar `{edition}/YYYY/MM/index.html`, weeks `{edition}/week/`, briefings `{edition}/briefing/`, `{edition}/feed.xml` (RSS), `{edition}/about.html`; the site contract is `lambdas/build/SITE.md`. The brand is a codename set only in `site.yaml`.
- `make replay` rebuilds the windows and site from all raw batches. `make raw` lists the S3 objects with sizes. The static site is at `data/s3/seer-site/index.html`.
- Legacy: `make build-legacy up-legacy`, then `make cluster` (threshold experiments) or `make compare` (database-free stories against the Postgres ones).
- Each run's step outputs and timings land in `out/pipeline-<UTC>.json`.

**Knobs:** Compose environment of `fn-scrape` (`HOURS`, `REFRESH_HOURS`, `MAX_REFRESH_PER_SOURCE`, `RECHECK_MINUTES`, …) and `fn-build` (`STORY_*`, `WINDOW_HOURS`, `STATE_HOURS`, `CHANGE_MIN_RATIO`, `TOP_LIMIT`, `LATEST_LIMIT`, `MIN_SOURCES`, `SITE_CACHE_SECONDS`).

## Conventions

- **Where things go.** Prototypes go in `tests/` and research write-ups in `docs/`. Seer doesn't depend on Orion's code or stack.
- **Python.** 3.12, type hints, black and flake8 at line length 120, exact pins in `requirements.txt`. Keep comments minimal: one short line, only when the code isn't obvious.
- **Contract first.** For multi-part changes, the schema, `sources.yaml`, `categories.yaml`, Compose env variables and Makefile targets are fixed first. Components are then written against them, in parallel if useful.
- **Exploration workflow.** Open a PR, build, test (`make build up`, run the affected targets, check the viewer), then merge. Don't wait on watchers. CI skips changes that only touch `seer/` (`paths-ignore` in `.github/workflows/ci.yml`), so lint locally.
- **Git.** Commits use the user's git identity, never the agent's. Attribution goes on the PR.

## Scraping rules

- **Honest user agent:** `SeerBot/0.1`. Rate limit: 1 request per 2 s (`REQUEST_DELAY_S`).
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
- **Containers reach the internet only through the HTTPS proxy.** `docker-compose.proxy.yml` adds host networking, proxy variables and the CA. The Makefile uses it when `HTTPS_PROXY` is set.
- **Compose v5 builds through bake,** which needs `--allow=network.host`. `make build` handles that.
- **Docker Hub can rate-limit base-image lookups (429).** Retry later or log in.
- **Disk fills up.** The build image is about 4.4 GB; `docker builder prune -f` and removing old images frees space.
- **Both Lambdas get the proxy.** Scrape fetches news; build fetches only thumbnails and logos. Both run on the host network: scrape's emulator on port 9101, build's on 9102 with its runtime API moved to 9003, because two host-network emulators clash on the default 9001.
- **The Lambda emulator takes one call at a time** and crashes on concurrent calls to the same container. The runner serializes calls per function; real Lambda scales out.

## Open questions

- A subject and region fallback per edition: fixed vectors per category, or the edition's home region.
- A minimum vote for categories, for example 2 or more votes and at least 20% of a story's articles.
- Syndication fingerprints, so agency copy counts once.
- A more stable extraction or a text-normalization step, so Le Figaro stops raising false "updated" flags.
- Images. Linking to outlets' images is fine for the prototype but needs a legal check before going public, since agency photos are licensed.
- Linking stories that continue past the 24 h span into one longer topic thread.
- Linking the same story across editions. The US airspace story appears in both mk and fr today.
- Labelled pairs to measure precision and recall properly.
