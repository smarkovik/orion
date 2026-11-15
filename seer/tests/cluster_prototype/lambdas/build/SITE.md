# Public site: contract

The build Lambda renders a public, static website next to the existing analysis pages, which move to `/lab/`. Settings and all interface text are in `site.yaml`; the brand name is a codename and appears nowhere else.

**Readers:** non-technical, mostly 30–60. The UI is clean and simple and shows what happened: a picture and a title per story, how many outlets covered it, and links to read more at the outlets. Large type, high contrast, big tap targets, no jargon, no tiny chips. Light and dark themes: follow the system, with a toggle that remembers the choice. Mobile first. No search; history is browsed by day.

## Pages (site bucket `SITE_BUCKET`)

| Key | Page | Rendered |
| --- | --- | --- |
| `index.html` | Edition chooser: brand, one big link per edition with its tagline | every build |
| `{e}/index.html` | Front page: lead story (large picture), then the top `limits.front` stories by score with ≥ `min_sources` sources; section links; link to today's day page and the calendar | every build |
| `{e}/s/{slug}.html` | Section: top `limits.section` stories whose region (mk) or subject (fr), per `section_facet`, equals the section name | every build |
| `{e}/story/{n}.html` | Story (`n` = the number after the edition in the story id): picture with credit, title, "N sources", time range, "first reported by …", then every article: outlet, title, time, a "Read on {outlet}" link to the original. Updated/new markers. Links to its day page and section | each build, for every story shown on a rendered page or touched this run |
| `{e}/{YYYY}/{MM}/{DD}.html` | Day: the day's top `limits.day` stories, previous/next day links, link to the month calendar | today and yesterday (edition time zone), every build |
| `{e}/{YYYY}/{MM}/index.html` | Month calendar: one cell per day with that day's lead title and story count, linking to the day page; previous/next month | the current month every build; the previous month during the first 2 days of a month |
| `{e}/about.html` | About and the list of outlets (from `sources.yaml`), contact line | every build |
| `{e}/feed.xml` | RSS 2.0, top `limits.feed` stories, linking to story pages | every build |
| `assets/site.{hash}.css`, `assets/site.{hash}.js` | One stylesheet, one small script (theme toggle; ← → keys on day pages). `hash` = first 10 hex of sha1 of the content | every build (same key while unchanged) |
| `thumbs/{sha1(src)[:16]}.webp` | One thumbnail per story: 640×360, cover-cropped, WebP | by `thumbs.ensure` |
| `robots.txt`, `sitemap.xml` | `Disallow: /lab/`; sitemap of front, sections, about, the last 30 day pages per edition and the story pages of open stories (only when `base_url` is set; otherwise skip the sitemap) | every build |
| `lab/index.html`, `lab/{e}/index.html`, `lab/{e}/latest.html` | Today's analysis pages, moved; `<meta name="robots" content="noindex">` | every build |

- **Links are relative and name the file** (`../story/12.html`, `2026/11/15.html`), so the site works opened from disk, on S3 behind CloudFront and as a shared preview. No absolute paths, no directory URLs.
- **Single-source stories have no story page**: their card links straight to the article.
- **Top of the day** = open or archived stories in the window whose `first_published`, in the edition's time zone, falls on that day, with ≥ `min_sources` sources, ranked by source count, then size, then `first_published`.
- **Thumbnail missing** (`thumb_key` empty): a calm placeholder block, never a broken image. Images get `alt` = the title, `loading="lazy"` (except the lead), and width/height so the layout doesn't jump.
- **Times** are shown in the edition's time zone and language: `14:20` for today, `15 ноември, 14:20` / `15 novembre, 14:20` otherwise. Dates use `months` and `weekdays` from `site.yaml`.
- **Cache-Control** from `cache_seconds`: `html` for pages and feeds, `past_day` for day pages older than yesterday (never re-rendered anyway), `asset` (+ `immutable`) for hashed assets and thumbnails.
- No external requests: no web fonts, no CDNs, no trackers. System font stack.

## Modules

| File | Owner | Holds |
| --- | --- | --- |
| `build/model.py` | fixed | `Story.thumb_key`, `thumb_src`, `thumb_source`; `days_key(edition)` |
| `build/web/` (`render.py`, `templates/`, `static/`) | web agent | `selection(window, cfg, now) -> list[str]` (story ids that any page rendered this run will show), `day_stories(window, day, cfg) -> list[Story]` (the ranking above; `day` is a `date` in the edition's time zone), `render_edition(window, cfg, now, days, sources, touched) -> list[Page]`, `render_root(cfg, summaries, now) -> list[Page]` (chooser, robots, sitemap), `render_assets() -> (list[Page], css_key, js_key)`. `Page` = `(key, body: bytes, content_type, cache_control)`. `cfg` = parsed `site.yaml` plus `"edition": code`. `days` = the edition's days index (below). `sources` = `{domain: name}` from `sources.yaml` |
| `build/thumbs.py` | thumbs agent | `ensure(window, story_ids, now) -> dict` (counts: fetched, reused, failed, skipped): for stories with `thumb_key is None`, try the label article's `image_url`, then the other members' images (newest first); download (honest user agent, 10 s timeout, ≤ 8 MB, `image/*` only), cover-crop to 16:9, resize to 640×360, WebP quality 72, upload to the site bucket; set `thumb_key`, `thumb_src`, `thumb_source` (the article's domain). If none works, `thumb_key = ""`. Up to `THUMBS_PER_RUN` (default 80) downloads per run, 8 in parallel, at most 2 at once per host |
| `build/days.py` | thumbs agent | `update(window, cfg, now, previous) -> list[dict]` maintaining `state/{edition}/days.json`: one entry per day, newest first, `{"date", "stories", "lead_title", "lead_story", "lead_thumb"}`, updated for today and yesterday using `web.render.day_stories`; kept 3 years |
| `build/render.py` | thumbs agent | Lab pages: same as now, keys under `lab/` and `noindex` |
| `build/handler.py` | thumbs agent | After assign and prune: `selection` → `thumbs.ensure` → `days.update` → `render_assets`, `render_edition`, `render_root`, lab pages → upload every `Page` with its content type and cache header → save `days.json` with the window |

## Local run

`fn-build` now needs the internet for thumbnails. Behind the proxy it runs like `fn-scrape`: host network, proxy env, `NO_PROXY=127.0.0.1,localhost`, S3 at `http://127.0.0.1:7070`, the emulator on `0.0.0.0:9102` and its runtime API on `127.0.0.1:9003` (host-network emulators clash on the default 9001). `make preview` serves `data/s3/seer-site/` at http://localhost:8090.

## Retention

Site bucket lifecycle: `{e}/story/`, `{e}/20*` (day and month pages) and `thumbs/` expire after 1,095 days (3 years), like the archive.
