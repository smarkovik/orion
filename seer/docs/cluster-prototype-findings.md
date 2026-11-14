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

## Static categories

Each story gets one region and one subject by majority vote of its articles' WordPress categories. Those categories are mapped through `tests/cluster_prototype/categories.yaml`, which holds 4 regions, 9 subjects, regex rules by category name, and per-site overrides. No model is involved.

- **Every article has categories** (1,155 of 1,156), but sites file by place, not by subject. The most common are Македонија (377) and Свет (216). Subject sections are rare: Хроника 49, Економија 40, Политика 35. Catch-alls are common: Актуелно 129, ПЕЧАТЕНО ИЗДАНИЕ 43, Избор 38.
- **Coverage at 0.92**, across 194 stories with 2+ sources: **84% get a region and 49% get a subject.**
    - Subjects assigned: Економија 25, Хроника 25, Политика 19, Лајфстајл 10, Сцена 7, Спорт 6, Технологија 2, Култура 2.
    - 98 stories get no subject.
- **Weak votes decide.** The diabetes story got Лајфстајл from 1 vote out of 12 articles, through one "Магазин" article.
- **Sites misfile.** A story about a global copper shortage was filed under Македонија.
- **No Albanian-language articles** appeared in the window. nezavisen.mk has Albanian categories, but none were used in these 48 hours.

**Conclusion.** Static allocation is good enough for region. For subject it needs:

1. **A minimum vote**, such as 2 or more votes covering at least 20% of the story's articles.
2. **A static fallback:** one fixed vector per subject, built from the stories that do get a subject vote. A story with no vote takes its nearest subject.
3. **A check** on 100 hand-labelled stories before trusting either.

## French edition

These are 10 French sources read from news sitemaps, with article text extracted by trafilatura and capped at 150 articles per source. They're clustered separately from Macedonian.

| | mk | fr |
| --- | --- | --- |
| Articles in 48 h | 1,158 | 1,189 |
| Stories with 2+ sources at 0.92 | 194 | 134 |
| Largest story at 0.92 | 24 | 30 |
| Region / subject coverage | 84% / 49% | 40% / 81% |

- **Scraping.** 1,187 articles with no fetch or extraction failures. Median text length is about 2,500 characters; BFMTV is the shortest at about 960. The cap of 150 per source covers only about 24 h for the busiest sites (Le Figaro, BFMTV, Le Parisien).
- **Threshold.**
    - 0.92 suits French too.
    - At 0.90 a Teddy Riner story absorbed a separate set of reactions to Macron (31 articles).
    - At 0.94 single stories start to split, and stories with 2+ sources drop from 88 to 79 in the clusterer agent's run on part of the data.
- **Good merges:** US airspace closure (30 articles, 10 sources), Microsoft outage (18, 9) and Meta's fine in Italy (5, 5).
- **Categories mirror Macedonian.**
    - French sites file by subject: politique, economie, societe, sports.
    - Macedonian sites file by place.
    - So each edition needs a fallback for its weak facet. For fr's region, the edition's home region is a reasonable default.
- **Cross-edition overlap.** The US airspace story leads both editions. That's a natural first case for linking stories across editions.

## Stable stories, images and updates

The live pipeline now adds only new articles to stable stories (`make stories`), instead of re-clustering 48 hours every run.

- **First design: compare each article to the story's mean vector.** It joined if that cosine was 0.92 or more, and articles had to be within 18 h of the story's newest article. This drifted. One mk story absorbed 96 articles across Mickoski, SDSM and Alta Banka, and daily weather forecasts still chained across days.
- **The fix has three parts:**
    1. Join on the article's average similarity to the story's members, which is the batch run's average-link rule.
    2. A 24 h span cap from the story's first article.
    3. Activity time taken from article and update times, not from the time of the run.
- **Result:**

| | mk | fr |
| --- | --- | --- |
| Stories with 2+ sources (batch run) | 194 (193) | 141 (134) |
| Largest story | 15 (was 96) | 28 |
| Longest span | 22 h | 23 h |

- **Weather now splits by day:** one story covers 13 November and another 14 November. The former mega-story became six stories of 7–13 articles each.
- **Idempotent:** a second run with no new articles changes nothing. Removing 50 articles' assignments and re-running put 32 into existing stories and 18 into new ones.
- **Images.** mk featured images cover 100% of recent articles. fr images, from sitemap `image:loc` or the page's `og:image`, cover 56–100% per site. The viewer links to the outlet's image URL with `referrerpolicy="no-referrer"` and removes broken images.
- **Updates.**
    - A change is meaningful if the title changed or the text similarity (difflib) dropped below 0.95. A halved body was flagged; one appended word was not.
    - fr articles from the last 6 h are re-fetched, at most 20 per source per run.
    - Le Figaro's extraction varies between fetches (ratio 0.93), so it produces false "updated" flags. A 48 h re-fetch flagged 17 of 111 Figaro articles against 2 of 863 for the other sites, enough to float the French top stories. Fix: a stricter ratio for that site, or normalizing the text before comparing.
- **"New" after a rebuild.** A story's creation time is when we formed it, so after `make reset-stories` every story shows "new" for 3 h. That's harmless for incremental runs, but a "new" badge could instead use the story's first article time.

## Infrastructure notes

- **Behind an HTTPS proxy,** containers need host networking, the proxy variables and the proxy's CA. That's `docker-compose.proxy.yml`.
- **Compose v5 builds through bake**, which refuses host-network builds unless granted. `run.sh` uses `docker compose build --print` piped into `docker buildx bake --allow=network.host`.
- **The model downloads into a named volume** at first use. It's about 1 GB and isn't baked into the image.

## How it was built

Three Sonnet agents wrote the scraper, clusterer and viewer in parallel, against a contract fixed in advance: the schema, Compose services and env variables. The orchestrator then built the containers, ran everything end to end, and checked the results. Each component was linted with black and flake8 at line length 120.
