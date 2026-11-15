# Adding a source or a country

Everything a source or an edition needs lives in three files in `tests/cluster_prototype/`:

- `sources.yaml`: where to read articles from
- `categories.yaml`: how a site's categories map to ours
- `site.yaml`: how the edition looks on the public site (`editions.<code>`)

No code changes are needed. The files are baked into the Lambda images (Compose also mounts them for local runs), so a deployed change needs a new image; the deploy workflows build one on every push.

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
make scrape EDITION=<code>        # the log line shows listed, fetched, failures per source
make site EDITION=<code>          # build from the new manifest; or `make refresh` for both steps
make preview                      # http://localhost:8090
```

Check the outlet on the edition's `about.html`, a story page that includes it, and `/system/admin/` (sources table).

## Add a country (edition)

An edition is one language plus one market, clustered on its own.

1. **Code.** Use the ISO 639-1 language code, for example `de`. It's the key in all three files and in S3 paths (`raw/de/...`).
2. **Sources.** Find 10 or more outlets that pass the checks above. Clustering needs several outlets covering the same event, so fewer than 10 gives thin stories.
3. **`sources.yaml`.** Add `editions.<code>` with `language: <code>` and the source list.
4. **`categories.yaml`.** Add `editions.<code>` with:
    - a `taxonomy` (regions, subjects)
    - `rules`: regexes on lowercased category names or URL sections
5. **`site.yaml`.** Add `editions.<code>` with:
    - `name`, `lang`, `timezone` (IANA, for example `Europe/Berlin`) and `tagline`
    - `section_facet` (`region` or `subject`) and `sections`: `{name, slug}` pairs, where `name` is a category from `categories.yaml`
    - `months` (12 names) and `weekdays` (7 names, Monday first)
    - `text`: every interface string. Copy an existing edition's block and translate all keys, including `about_body` and `privacy_body`.
6. **Infrastructure.** Add the code to `editions` in `infra/tofu/envs/*/terraform.tfvars`; that adds its schedule and site lifecycle rules.
7. **Language check.** e5 covers about 100 languages. For a new script, check the tokenizer the way `docs/tokenizer-research.md` does.
8. **Threshold.** The build threshold is `STORY_THRESHOLD` (0.92, suited both mk and fr). To test others, use the legacy batch experiment: `make up-legacy`, then `make cluster EDITION=<code> THRESHOLDS=0.90,0.92,0.94` and compare the runs in the viewer.
9. **Write up the numbers** in `docs/cluster-prototype-findings.md`: articles, stories with 2+ sources, category coverage, and good and bad merges.
10. **Before anything is public,** get a legal check for that market. France, for example, has a press publishers' right.
