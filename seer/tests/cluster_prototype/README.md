# Cluster prototype

First end-to-end test of Seer: scrape 10 Macedonian news sites, embed the articles, cluster them into stories, and inspect the clusters in a browser. Everything runs in Docker.

```bash
./run.sh          # db + viewer up, scrape the last 48 h, cluster at 3 thresholds
open http://localhost:8080
./run.sh down
```

Steps can also run alone: `./run.sh up`, `./run.sh scrape`, `./run.sh cluster`.

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
- **Proxy sandboxes.** `docker-compose.proxy.yml` adds host networking, proxy variables and an extra CA for environments behind an HTTPS proxy; `run.sh` uses it when `HTTPS_PROXY` is set.
