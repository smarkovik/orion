# Adding a source or a country

Everything a source or an edition needs lives in two files in `tests/cluster_prototype/`:

- `sources.yaml`: where to read articles from
- `categories.yaml`: how a site's categories map to ours

You only touch code to give a new edition a display name in the viewer.

## Add a source to an existing edition

1. **Pick the method.** Use the first one that works.

| Method | Check | Gives |
| --- | --- | --- |
| `wp_api` | `curl -s "https://SITE/wp-json/wp/v2/posts?per_page=1"` returns JSON | Title, date, full text and categories in one call |
| `news_sitemap` | robots.txt has a `Sitemap:` line containing `news`, and the file lists recent `<news:publication_date>` entries | URL, title and date. Text comes from fetching each article page. |

Anything else, such as RSS only or homepage links only, isn't supported in this prototype yet. `tests/scraper/latest_news.py` has prototypes of both.

2. **Check that the site lets us read it.**
    - Fetch one article page with `curl -A "Mozilla/5.0 (compatible; SeerBot/0.1)"`.
    - A 402 or 403, a "Just a moment..." page (Cloudflare) or `dd={` (DataDome) means the site is blocked. Leave it out.
    - Note any Crawl-delay in its robots.txt.
3. **Add it to `sources.yaml`** under the edition:

```yaml
- {name: "Le Figaro", domain: lefigaro.fr, base_url: "https://www.lefigaro.fr", method: news_sitemap,
   sitemap_url: "https://www.lefigaro.fr/sitemap_news.xml"}
```

4. **Map its categories in `categories.yaml`.**
    - `wp_api` sites: list their categories with `curl "https://SITE/wp-json/wp/v2/categories?per_page=100&orderby=count&order=desc"`.
    - `news_sitemap` sites: the category is the first section of the URL path, for example `faits-divers` or `international`.
    - Add patterns to the edition's `rules` if they're general. Put a one-site exception under `domains:` (a mapping, or `null` to ignore).
    - Leave catch-alls (Актуелно, info-en-continu) unmapped.
5. **Run and inspect:**

```bash
make scrape EDITION=<code>        # the log line shows in_window, fetched, extraction failures
make cluster EDITION=<code>
make stats && make open
```

## Add a country (edition)

An edition is one language plus one market, clustered on its own.

1. **Code.** Use the ISO 639-1 language code, for example `de`. It's stored in `sources.language` and `cluster_runs.edition`.
2. **Sources.** Find 10 or more outlets that pass the checks above. Clustering needs several outlets covering the same event, so fewer than 10 gives thin stories.
3. **`sources.yaml`.** Add `editions.<code>` with `language: <code>` and the source list.
4. **`categories.yaml`.** Add `editions.<code>` with:
    - a `taxonomy` (regions, subjects)
    - `rules`: regexes on lowercased category names or URL sections
5. **Viewer name.** Add the code to `EDITIONS` in `viewer/app.py`, for example `"de": "Deutschland"`.
6. **Language check.** e5 covers about 100 languages. For a new script, check the tokenizer the way `docs/tokenizer-research.md` does.
7. **Threshold.** Run `make cluster EDITION=<code> THRESHOLDS=0.90,0.92,0.94` and compare the runs in the viewer. 0.92 suited both mk and fr.
8. **Write up the numbers** in `docs/cluster-prototype-findings.md`: articles, stories with 2+ sources, category coverage, and good and bad merges.
9. **Before anything is public,** get a legal check for that market. France, for example, has a press publishers' right.
