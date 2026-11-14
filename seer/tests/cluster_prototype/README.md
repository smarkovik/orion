# Cluster prototype

First end-to-end test of Seer: scrape 10 Macedonian news sites, embed the articles, cluster them into stories, and inspect the clusters in a browser. Everything runs in Docker.

```bash
make all          # build, start, scrape the last 48 h, cluster at 3 thresholds, open the viewer
make down         # stop; data is kept
```

`make` alone lists every target. `./run.sh <target>` is a shortcut for the same thing.

| Target | Does |
| --- | --- |
| `all` | Build, start, scrape, cluster, then open the viewer |
| `build`, `up`, `down`, `restart` | Build the images; start the database and viewer; stop everything; restart the viewer |
| `scrape`, `cluster`, `refresh` | Run the scraper, run the clusterer, or both |
| `open` | Open http://localhost:8080 in a browser |
| `ps`, `logs`, `health` | Container status; follow logs (`SERVICE=viewer`); check the viewer and the database |
| `stats`, `sql`, `psql` | Articles per source and recent runs; one query (`SQL="..."`); an interactive shell |
| `clear-runs` | Delete cluster runs but keep articles and embeddings |
| `clean` | Stop and delete all data, including the model cache |

Per-run overrides: `make scrape HOURS=6`, `make cluster THRESHOLDS=0.91,0.92`. `WINDOW_HOURS` and `MODEL` work the same way.

## Services

| Service | Does | Runs |
| --- | --- | --- |
| `db` | Postgres 16 + pgvector 0.8.7; schema in `db/schema.sql` | Always; host port 5433 |
| `scraper` | Reads `sources.yaml`, pulls the last `HOURS` of posts from each site's WordPress API, upserts `articles` by canonical URL | One-shot job |
| `clusterer` | Embeds new articles with `intfloat/multilingual-e5-base` (CPU), then average-link clustering at each threshold in `THRESHOLDS`; one `cluster_runs` row per threshold | One-shot job |
| `viewer` | Read-only web page: runs, clusters per run, articles per cluster | Always; port 8080 |

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
