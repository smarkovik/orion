# Cluster prototype

An end-to-end test of Seer in Docker. It scrapes two editions of 10 news sites each, Macedonian (`mk`) and French (`fr`), embeds the articles, and clusters each edition into stories. You can then inspect the stories side by side in a browser. To add a source or a country, see [the guide](../../docs/adding-sources-and-editions.md).

```bash
make all          # build, start, run the Lambda pipeline (scrape, ingest, stories, export), open the viewer
make down         # stop; data is kept
```

`make` alone lists every target. `./run.sh <target>` is a shortcut for the same thing.

| Target | Does |
| --- | --- |
| `all` | Build, start, run the whole pipeline, then open the viewer |
| `build`, `up`, `down`, `restart` | Build the images; start the database, S3, the four Lambda containers and the viewer; stop everything; restart the viewer |
| `scrape`, `stories`, `site`, `refresh` | Scrape to S3 and ingest; add new articles to stable stories; export the static site to S3 (prints `data/s3/seer-site/index.html`); or all four steps |
| `raw` | List raw objects, manifests and state under `data/s3/seer-raw`, with sizes |
| `cluster` | Batch experiment: re-cluster the whole window at each threshold (`cluster_runs`) |
| `reset-stories` | Delete all stories so the next `make stories` rebuilds them |
| `open` | Open http://localhost:8080 in a browser |
| `ps`, `logs`, `health` | Container status; follow logs (`SERVICE=viewer`); check the viewer and the database |
| `stats`, `sql`, `psql` | Articles per source and recent runs; one query (`SQL="..."`); an interactive shell |
| `migrate` | Apply `db/schema.sql` to the running database (`up` does this too) |
| `export` | Save a run page as static HTML in `out/` (`RUN=<id>`, `MIN_SOURCES=2`) |
| `export-editions` | Save the side-by-side stories page, with tabs, to `out/editions.html` (`VIEW=top` or `latest`) |
| `clear-runs` | Delete cluster runs but keep articles and embeddings |
| `clean` | Stop and delete all data, including the model cache and `data/s3` |

Per-run overrides: `make scrape HOURS=6`, `make cluster THRESHOLDS=0.91,0.92`. `make refresh EDITION=fr` limits a run to one edition (`--editions`). `WINDOW_HOURS` and `MODEL` apply to `make cluster`; scrape knobs such as `MAX_ARTICLES_PER_SOURCE` live in the `fn-scrape` environment in `docker-compose.yml`.

## Services

| Service | Does | Runs |
| --- | --- | --- |
| `db` | Postgres 16 + pgvector 0.8.7; schema in `db/schema.sql` | Always; host port 5433 |
| `s3` | versitygw, a local S3 stand-in; objects are plain files under `data/s3/` | Always; port 7070 |
| `fn-scrape` | Lambda: fetches each source into one raw object per edition per run. No database. | Invoked on port 9101 |
| `fn-ingest` | Lambda: parses the raw object, upserts `articles` by canonical URL, rebuilds `state/` | Invoked on port 9102 |
| `fn-stories` | Lambda: embeds new articles with `intfloat/multilingual-e5-base` (CPU) and joins stable stories | Invoked on port 9103 |
| `fn-export` | Lambda: renders the static site into the site bucket | Invoked on port 9104 |
| `clusterer` | Batch experiments (`make cluster`). Embeds new articles with `intfloat/multilingual-e5-base` (CPU), then clusters each edition on its own, with average-link clustering at each threshold in `THRESHOLDS`. Writes one `cluster_runs` row per edition and threshold. | One-shot job |
| `viewer` | Read-only web pages: runs, the clusters in each run, and the articles in each cluster. `/editions` shows every edition in CSS tabs. | Always; port 8080 |

## Lambda pipeline

The hourly pipeline runs as four Lambda container images behind AWS's Runtime Interface Emulator. `pipeline/run_pipeline.py` (standard library only) stands in for Step Functions: scrape then ingest per edition, then stories, then export. It writes every step's output to `out/pipeline-<timestamp>.json`. The emulator handles one call at a time, so calls to the same function run one after another. `infra/` holds the matching Step Functions definition and S3 lifecycle files. Contract and S3 layout: [lambdas/README.md](lambdas/README.md).

Only `fn-scrape` has internet access (host network behind the proxy). The other three run on the default network without a proxy, which shows they need none.

## Categories

`categories.yaml` holds a static category list for each edition: mk has 4 regions and 9 subjects, fr has 3 regions and 10 subjects. Each site's source categories map to that list through regex rules, plus per-site overrides. For mk, source categories are WordPress category names; for fr, they're URL sections. Catch-all categories map to nothing. The clusterer gives each story the majority region and subject of its articles, and the viewer shows them as badges and filters. Results are in [the findings](../../docs/cluster-prototype-findings.md#static-categories).

## Choices

- **10 sources, one language.** Clustering needs several outlets covering the same event, so all 10 are Macedonian. All expose the WordPress posts API with full text, so no article pages are fetched.
- **Several thresholds per run.** The right cosine threshold for e5 is unknown, so each run stores one result per threshold and the viewer lets you compare them.
- **robots.txt is ignored** (`IGNORE_ROBOTS=true`) for experiments only. Requests stay at 1 per 2 s per host and the bot identifies itself.
- **Proxy sandboxes.** `docker-compose.proxy.yml` adds host networking, proxy variables and an extra CA for environments behind an HTTPS proxy. `run.sh` uses it when `HTTPS_PROXY` is set, and builds images with `docker buildx bake --allow=network.host`, because Compose's builder won't run a host-network build without that grant.

## Results (2026-11-14, 48 h window)

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
