# Reader statistics: contract

Answers seven questions on the system page (`/system/admin/`): returning-reader %, what returning readers read, what everyone reads, trends (daily, weekly, monthly), what's never read, time on page, and devices.

**Privacy shape:**
- **No identifiers of any kind:** no ID, no fingerprint, no cookies, no IP use.
- **The browser keeps a few dates** in localStorage and sends flags with a small first-party ping.
- **Raw logs are deleted** right after processing.
- **Only counts are kept**, for 400 days.
- **Opt-out:** a "don't count my visits" switch in the display panel, explained in a short privacy note on the about page.

## 1. Ping (browser → CloudFront log)

`site.js` requests `system/p.gif` (path relative to the page, like other assets) with a query string, using `new Image()` for views and `fetch(url, {keepalive: true, cache: "no-store"})` for leave, "read on", share and follow events (`new Image()` when `fetch` is missing). `system/p.gif` is a 43-byte transparent GIF in the site bucket (`Cache-Control: no-store`). CloudFront logs every request, including its query string, so the ping needs no server code.

| Param | Meaning |
| --- | --- |
| `v` | `1` (format version) |
| `e` | `v` view · `l` leave (time on page) · `o` "read on" click · `s` share · `f` follow |
| `ed` | edition code |
| `k` | page kind: `front`, `section`, `story`, `day`, `week`, `briefing`, `calendar`, `about`, `chooser` |
| `p` | page key relative to the site root, e.g. `mk/story/123.html` (from the page's own metadata, not `location`) |
| `st` | story id (`mk-123`) on story pages and for `o`/`s`/`f` events from cards or story pages |
| `sec` | section name of the page or story, if any |
| `n` | `1` = returning browser (first visit was on an earlier day), `0` = new |
| `fd`, `fw`, `fm` | `1` on this browser's first view today / this ISO week / this month (views only) |
| `t` | visible milliseconds on the page, capped at 1,800,000 (leave only) |
| `tm` | `1` when the user agent contains `Macintosh` and `navigator.maxTouchPoints > 1` (an iPad reporting a Mac); sent on view and leave pings only |
| `o` | outlet domain (`o` events) |
| `id` | random token for this page load only (never stored), to join a leave to its view |

- **Storage:** localStorage `{brandslug}:stats` = `{"first": "YYYY-MM-DD", "day": "YYYY-MM-DD", "week": "YYYY-Www", "month": "YYYY-MM"}`, in the browser's local date.
- **Opt-out:** `{brandslug}:nocount` = `"1"` disables every ping and clears `{brandslug}:stats`. All storage access is wrapped in try/catch; if storage fails, send nothing.
- **Leave:** one leave per page load, at the first `visibilitychange` to hidden or `pagehide`. It carries the visible time accumulated so far.
- **Service worker:** it registers a static route (`addRoutes`, source `network`) for `system/p.gif`, so the leave ping is not lost while the page unloads (Chromium drops such requests when they pass through a service worker).
- **Page metadata:** every page renders `<meta name="seer:page" content="{key}">`, `seer:kind`, `seer:edition`, `seer:story` and `seer:section` (empty when not applicable).

## 2. Logs → counts (build Lambda, every run)

`readers.py` exposes `process(cfg, now, windows) -> dict` (stats for the build report). It never raises.

- **Input:** CloudFront standard logs (W3C, tab-separated; `#Fields:` header names the columns; `.gz` or plain), from `LOGS_DIR` when set (local), else S3 `LOGS_BUCKET` (default `RAW_BUCKET`) under `LOGS_PREFIX` (default `logs/cloudfront/`).
- **Fields used:** `date`, `time`, `cs-uri-stem`, `cs-uri-query`, `sc-status`, `cs(User-Agent)`. `c-ip` is never read.
- **Filtering:** pings are requests for `/system/p.gif`. Requests for `*.html` with status 200 whose first path segment is an edition code count as `server_html` (all page requests, including readers without JavaScript). Pings with an unknown edition, event, kind or page key, or a bad `t`, are dropped. User agents matching `bot|spider|crawl|slurp|preview|monitor` are dropped.
- **After aggregation:** write the day files, then the cursor (`state/readers_cursor.json` in the raw bucket, `{"done": [file names]}`), then delete the processed log files, then the index. A run that fails after the day files can at worst count those files again; a file that can't be read is left for the next run.
- **Day:** the date in the edition's time zone.

**Output, site bucket** (served with the system page; `Cache-Control: no-cache`):

`system/admin/data/readers/{edition}/{YYYY-MM-DD}.json`:
```json
{"v": 1, "edition": "mk", "date": "2026-11-15", "updated": "<iso>",
 "views": 0, "views_returning": 0, "server_html": 0,
 "readers_day": 0, "returning_day": 0, "first_week": 0, "first_month": 0,
 "kinds": {"story": {"views": 0, "views_returning": 0, "time": {"n": 0, "sum_ms": 0, "hist": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}}},
 "sections": {"Политика": {"views": 0, "views_returning": 0}},
 "stories": {"mk-123": {"views": 0, "views_returning": 0, "out": 0, "time_n": 0, "time_sum_ms": 0}},
 "outlets": {"nezavisen.mk": {"out": 0}},
 "pages": {"mk/index.html": 0},
 "events": {"share": 0, "follow": 0},
 "devices": {"phone": {"views": 0, "views_returning": 0, "readers_day": 0, "returning_day": 0,
                       "story_time": {"n": 0, "sum_ms": 0, "hist": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
                       "os": {"Android": {"views": 0, "readers_day": 0}},
                       "browsers": {"Chrome": {"views": 0, "readers_day": 0}}},
             "tablet": {}, "desktop": {}}}
```

**Device classification** (`ua.py`, `classify(ua, touch_mac) -> (device, os, browser)`): the raw `cs(User-Agent)` is URL-decoded (twice if still encoded). Device: iPhone/iPod, Android with `Mobile`, other `Mobile` / `Windows Phone` = phone; iPad, Android without `Mobile`, `Tablet`, Mac with `tm=1` = tablet; else desktop. OS: iOS, iPadOS (iPad, or Mac with `tm=1`), Android, Windows, macOS, ChromeOS, Linux, Other. Browser, first match: Facebook app, Instagram app, Edge, Opera, Samsung Internet, Firefox, Chrome, Safari (`Safari/` with `Version/`, or iOS WebKit), Other. Nothing is stored in the browser; bot filtering is unchanged.

- **`readers_day`:** views with `fd=1`. **`returning_day`:** those with `fd=1` and `n=1`. Returning % for a day = `returning_day / readers_day`.
- **`first_week`, `first_month`:** views with `fw=1` / `fm=1`. Weekly readers = the sum of `first_week` over the week's days; monthly readers likewise.
- **`devices`:** per device kind (`phone`, `tablet`, `desktop`; rows created on first use), from ping events only. Views (`e=v`) add to `views`, `views_returning`, `readers_day` (`fd=1`), `returning_day` (`fd=1` and `n=1`) and the `os` / `browsers` rows (`views`, `readers_day`); leaves on story pages add to `story_time` (same histogram as `time`). Classification is in `ua.py`, see "Device classification". Day files without `devices` still load.
- **Time histogram** upper bounds in seconds: 5, 10, 20, 30, 60, 120, 300, 600, 1800, then above (10 buckets). Medians are read from the histogram.
- **`pages`:** the top 200 page keys by views.
- **Merging:** a day file already in S3 is merged with the new counts (numbers and histogram buckets are added), so a day can be built from several runs.

`system/admin/data/readers/stories.json`: a catalog of stories with their own page, for titles and never-read. It's updated by each build from its edition's window and keeps entries whose `first_published` is within 35 days:
```json
{"updated": "<iso>", "stories": {"mk-123": {"edition": "mk", "title": "...", "section": "...", "sources": 5,
  "outlets": ["nezavisen.mk", "..."], "first_published": "<iso>", "page": "mk/story/123.html"}}}
```

`system/admin/data/readers/index.json`: `{"updated", "editions": {code: {"days": [dates newest first]}}}`, rebuilt each run from a listing of the day files, so a lost or broken index heals itself.

**Never read** = catalog stories older than 24 h with 0 views and 0 `out` across all day files since their `first_published`.

## 3. System page: "Readers" section

Same window selector (14 / 30 / 90) and edition filter as the rest of the page.
- **Tiles:** readers today, returning % today, views today, median time on story pages today, each with its 7-day average.
- **Trend charts:**
  - daily readers (bars) with returning % (line);
  - weekly readers and monthly readers;
  - views per day by page kind and by section.
- **What readers read:** a sortable table of the top 30 stories (title, edition, section, views, returning share, "read on" clicks, median time), with a toggle between all readers and returning readers. Next to it, section shares for new vs returning readers.
- **Never read:** count and share of stories never opened, by section and by outlet, plus the list of the top 20 never-read stories (most outlets first).
- **Devices (after Trends):** readers per day stacked by device kind (with table view); table "By device" (readers, share, views, returning %, median time on story pages); "Which kind": OS and browser shares of readers per device kind as horizontal bars. One-line definition under the block.
- **Time on page:** median and distribution by page kind.
- **Definitions:** a one-line note under each block.

## 4. Local run

`make preview` serves the site with `tools/preview_server.py` (standard library). It writes one CloudFront-format log line per request to `data/logs/cloudfront/` (hourly files, same `#Fields:` header). `fn-build` mounts `./data/logs` at `/logs` with `LOGS_DIR=/logs`.

In AWS, CloudFront standard logging (v2, W3C, tab-separated) writes to `s3://<raw-bucket>/logs/cloudfront/`; the OpenTofu stack sets this up and selects the fields. Leave out `c-ip` if you set it up by hand. A lifecycle rule deletes `logs/` after 7 days as a safety net.
