# Cluster prototype findings

2026-11-14 · Prototype: [`tests/cluster_prototype/`](../tests/cluster_prototype/README.md)

The full pipeline works on 10 Macedonian sites: scrape, embed, cluster and view, all in Docker. With multilingual-e5-base and average-link clustering, a cosine threshold of 0.92 gives clean same-event stories for most articles. The remaining errors are recurring topics and agency copy, and both have known fixes.

## Setup

| Part | Choice |
| --- | --- |
| Sources | 10 Macedonian news sites, all with an open WordPress posts API: nezavisen, vocentar, racin, press24, infomax, plusinfo, zurnal, libertas, 24info, novamakedonija |
| Window | The last 48 h: 1,240 articles scraped, 1,217 inside the clustering window |
| Embeddings | `intfloat/multilingual-e5-base` on CPU, `query: ` prefix (from the model card), title plus the first 1,200 characters of text |
| Clustering | scikit-learn average-link hierarchical clustering on cosine distance, run once per threshold |
| Storage | Postgres 16 with pgvector 0.8.7; vectors are cached per model and content hash |

## What we learned

1. **The WordPress API is enough for Macedonian sites.** It returns full text, so no article pages were fetched. All 10 sites took 6 s in total, at 1 request per 2 s per host, and re-runs are idempotent.
2. **CPU embedding is fast enough for a prototype.** It runs at about 3.9 articles per second, so a day of articles from 10 sites (about 600) takes under 3 minutes. Cached vectors make every later run take seconds.
3. **e5's similarity scores sit in a narrow, high band.** Thresholds that look strict aren't:

| Threshold | Clusters | With 2+ sources | Largest |
| --- | --- | --- | --- |
| 0.82 | 12 | 11 | 897 |
| 0.86 | 198 | 121 | 154 |
| 0.90 | 479 | 174 | 35 |
| **0.92** | **583** | **195** | **23** |
| 0.94 | 686 | 204 | 19 |

4. **0.92 is the sweet spot for this model.**
    - **Below 0.92**, related stories merge. At 0.90, Ukraine talks, NATO and Donbas all formed one 35-article cluster.
    - **Above 0.92**, single stories start to split. The IMF ranking story split at 0.94, and stories with 2 or more sources peak at 0.94 and drop at 0.95.
    - **At 0.92**, 66.8% of articles are in stories with 2 or more sources. A random sample of 4 stories with 3 or more sources was each a single event.
5. **Failure modes at 0.92:**
    - **Recurring topics merge across days.** Daily weather forecasts formed one 23-article cluster over two days.
    - **Topic versus event.** World Diabetes Day features joined a minister's statement on diabetes.
    - **Agency copy.** Identical titles from several outlets inflate a story's source count.
    - **All-caps titles.** plusinfo.mk and vocentar.com write titles in capitals, so they make poor headlines as-is.

## Next steps

1. Cap how far apart in time a story's articles can be, for example 24 h from the story's first article, or link only within days. This targets the weather merge.
2. Fingerprint syndicated text (MinHash) so agency copy counts once toward a story's sources.
3. Build the labelled set of 300 pairs from this data and measure precision and recall, instead of spot checks.
4. Try named entities as a second signal for topic-versus-event merges.
5. Convert all-caps titles to normal case when choosing headlines.

## Infrastructure notes

- **Behind an HTTPS proxy,** containers need host networking, the proxy variables and the proxy's CA. That's `docker-compose.proxy.yml`.
- **Compose v5 builds through bake**, which refuses host-network builds unless granted. `run.sh` uses `docker compose build --print` piped into `docker buildx bake --allow=network.host`.
- **The model downloads into a named volume** at first use. It's about 1 GB and isn't baked into the image.

## How it was built

Three Sonnet agents wrote the scraper, clusterer and viewer in parallel, against a contract fixed in advance: the schema, Compose services and env variables. The orchestrator then built the containers, ran everything end to end, and checked the results. Each component was linted with black and flake8 at line length 120.
