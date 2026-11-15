# Cluster prototype

An end-to-end test of Seer in Docker. It scrapes two editions of 10 news sites each, Macedonian (`mk`) and French (`fr`), embeds the articles, and clusters each edition into stories, rendered as a public static site (contract: [lambdas/build/SITE.md](lambdas/build/SITE.md)) plus the analysis pages under `/lab/`. To add a source or a country, see [the guide](../../docs/adding-sources-and-editions.md).

```bash
make all          # build, start, scrape and build both editions, print the site path
make down         # stop; data is kept
```

`make` alone lists every target. `./run.sh <target>` is a shortcut for the same thing.

There is no database. Two Lambdas and S3 do everything; the contract is in [lambdas/README.md](lambdas/README.md).

| Target | Does |
| --- | --- |
| `all` | Build, start, run the pipeline, print the site path |
| `build`, `up`, `down`, `restart` | Build the two Lambda images; start S3 and the two Lambdas; stop everything (all profiles); restart the Lambdas |
| `docker` | Start the Docker daemon if it isn't running (cloud sandboxes); the other targets call it |
| `refresh` | Scrape, then build from the new manifest, per edition |
| `scrape` | Scrape to S3 only |
| `site` | Build from the latest manifest of each edition without scraping; prints `data/s3/seer-site/index.html` |
| `preview` | Serve `data/s3/seer-site` at http://localhost:8090 (`PREVIEW_PORT`) with `tools/preview_server.py`, which also logs each request to `data/logs/cloudfront/` for the reader statistics (`lambdas/build/READERS.md`); the analysis pages are under `/lab/`, the back-office page (run history, health, costs) at `/system/admin/` |
| `replay` | `EDITION=mk` (default both): delete the edition's window, summary and scrape state (not `days.json`), then build every manifest in `runs/` in order |
| `raw` | List `raw/`, `runs/`, `state/`, `archive/` and `builds/` under `data/s3/seer-raw`, with sizes |
| `ps`, `logs`, `health` | Container status; follow logs (`SERVICE=fn-build`); check the containers (and the viewer and database if up) |
| `clean` | Stop and delete all data, including `data/s3` |

Per-run overrides: `make refresh HOURS=6 EDITION=fr` (`--hours`, `--editions`). Scrape knobs such as `MAX_ARTICLES_PER_SOURCE` live in the `fn-scrape` environment and build knobs such as `STORY_THRESHOLD` in the `fn-build` environment in `docker-compose.yml`.

## Services

| Service | Does | Runs |
| --- | --- | --- |
| `s3` | versitygw, a local S3 stand-in; objects are plain files under `data/s3/` | Always; port 7070 |
| `fn-scrape` | Lambda: fetches each source into one raw object per edition per run, plus a manifest. Internet access only. | Invoked on port 9101 |
| `fn-build` | Lambda: ingests the raw object, embeds new articles with `intfloat/multilingual-e5-base` (CPU), joins stable stories, downloads story thumbnails and outlet logos, renders the public site and `/lab/` pages, writes the window, state, archive, back-office data and reader counts. Needs internet for thumbnails and logos. | Invoked on port 9102 |

## Lambda pipeline

Each hour from 08:00 to 22:00 (Europe/Skopje), per edition: scrape writes a raw object and a manifest to S3, the S3 event for the manifest invokes build, and build reads the edition's 48 h window from S3, updates it and writes the site, the window, the scrape state, an archive, a report, the back-office run summary and the reader counts. `pipeline/run_pipeline.py` (standard library only) stands in for the scheduler and the S3 event: it invokes scrape, then build with an S3-event payload for the new manifest. It writes every step's output to `out/pipeline-<timestamp>.json`. The emulator handles one call at a time, so calls to the same function run one after another. `--replay` (`make replay`) rebuilds an edition from its manifests. `S3_DIR` or `--s3-dir` points the runner at another S3 folder. The real AWS stack is OpenTofu in `seer/infra/tofu/`; `infra/` here keeps the earlier JSON and CLI definitions as reference ([infra/README.md](infra/README.md)).

`fn-scrape` and `fn-build` need internet access (scrape for the news sites, build for thumbnails); behind the proxy both run on the host network, on emulator ports 9101 and 9102 with runtime APIs on 9001 and 9003. Without internet the build still succeeds: stories get a placeholder instead of a picture and outlets a round initial instead of a logo. Settings and interface text of the public site are in `site.yaml`.

## Legacy (Postgres)

The earlier design kept articles, embeddings and stories in Postgres. It is still here under the Compose profile `legacy`: `db`, `viewer` and the batch `clusterer`. Use it for threshold experiments and to check the new results.

| Target | Does |
| --- | --- |
| `build-legacy`, `up-legacy` | Build the viewer and clusterer images; start Postgres and the viewer and apply the schema |
| `cluster`, `reset-stories` | Batch experiment (`THRESHOLDS`, `WINDOW_HOURS`, `MODEL`); delete all stories |
| `compare` | `tools/compare_stories.py` in the clusterer image: open stories in S3 (`state/{edition}/window.json.gz`) against Postgres, per edition, with pairwise co-assignment agreement. Run `up-legacy` first. |
| `stats`, `sql`, `psql`, `migrate`, `clear-runs` | Database helpers |
| `open`, `export`, `export-editions` | Viewer and its static pages |

The legacy Lambdas (`fn-ingest`, `fn-stories`, `fn-export`) are gone; the legacy database no longer receives new articles.

## Categories

`categories.yaml` holds a static category list for each edition: mk has 4 regions and 9 subjects, fr has 3 regions and 10 subjects. Each site's source categories map to that list through regex rules, plus per-site overrides. For mk, source categories are WordPress category names; for fr, they're URL sections. Catch-all categories map to nothing. Build (and the legacy clusterer) gives each story the majority region and subject of its articles, and the pages show them as badges and filters. Results are in [the findings](../../docs/cluster-prototype-findings.md#static-categories).

## Choices

- **10 sources per edition.** Clustering needs several outlets covering the same event, so each edition has 10 outlets in one language. The 10 Macedonian ones expose the WordPress posts API with full text, so no article pages are fetched. The 10 French ones are read from their news sitemaps and each article page is fetched.
- **Several thresholds per run (legacy).** The right cosine threshold for e5 is unknown, so each batch run stores one result per threshold and the viewer lets you compare them.
- **robots.txt is ignored** (`IGNORE_ROBOTS=true`) for experiments only. Requests stay at 1 per 2 s per host and the bot identifies itself.
- **Proxy sandboxes.** `docker-compose.proxy.yml` adds host networking, proxy variables and an extra CA for environments behind an HTTPS proxy. The Makefile uses it when `HTTPS_PROXY` is set, and builds images with `docker buildx bake --allow=network.host`, because Compose's builder won't run a host-network build without that grant.

## Results (2026-11-14, 48 h window, legacy Postgres run)

- **Scrape:** 1,240 posts from 10 sites in 6 s. A second run inserts only the new posts.
- **Embedding:** about 3.9 articles/s on CPU; 1,222 articles took 312 s. Vectors are cached in Postgres, so later runs only embed new articles.
- **Clusters**, over 1,217 articles in the window:

| Threshold | Clusters | With 2+ sources | Largest |
| --- | --- | --- | --- |
| 0.82 | 12 | 11 | 897 |
| 0.86 | 198 | 121 | 154 |
| 0.90 | 479 | 174 | 35 |
| **0.92** | **583** | **195** | **23** |
| 0.94 | 686 | 204 | 19 |

**0.92 works best.** e5 similarities sit in a narrow high band, so 0.82 puts 74% of articles into one cluster. At 0.92, 66.8% of articles land in stories with 2 or more sources. A random sample of 4 stories with 3 or more sources each covered a single event.

**What still goes wrong at 0.92:**

- **Recurring topics merge across days.** Daily weather forecasts formed one 23-article cluster spanning two days. Fix: a time limit within each story, or named entities.
- **Topic versus event.** World Diabetes Day features joined a minister's statement about diabetes.
- **Agency copy.** Several outlets carry identical titles, which inflates a story's source count. Fix: a syndication fingerprint.
- **All-caps titles.** plusinfo.mk and vocentar.com write titles in capitals. Headlines need normal casing.
