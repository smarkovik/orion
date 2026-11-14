# Latest-news scraper

2026-11-14 · Prototype: [`tests/scraper/latest_news.py`](../tests/scraper/latest_news.py)

Given a site URL, the scraper lists that site's latest articles with a title, URL and publish time. It works the same on Macedonian and French sites. Of 11 sites tested, 8 returned their latest news and 3 were correctly refused. The 11 sites took 17 seconds in total.

## How it works

1. **RSS or Atom feed.** Use the feed if the homepage advertises one or a common path has one (`/feed/`, `/rss`, `/rss.xml`, `/feed.xml`).
2. **Homepage links over plain HTTP.** Keep same-site links that look like articles:
    - the last part of the path has at least 4 hyphenated words, or the path holds an ID or a date (`_8281187.html`, `-20261114`, `/2026/11/14/`)
    - category, tag, author, newsletter and similar pages are skipped
    - when 5 or more links have an ID or date in the path, only those are kept
3. **Homepage via Lightpanda.** Used when plain HTTP finds fewer than 5 article links, which usually means the page builds its content with JavaScript.
4. **Dates.** Links found on the homepage carry no dates, so candidates are first ranked by any date in their URL. The top `3 × limit` article pages are then fetched to read their publish time from `article:published_time`, JSON-LD `datePublished` or `itemprop`.
5. **Politeness.** It respects robots.txt and sends an honest user agent (`SeerResearch/0.1`). Sites behind bot protection are reported as blocked, never bypassed.

## Results

| Site | Language | Method | Result |
| --- | --- | --- | --- |
| sdk.mk | mk | RSS | exact times |
| 24.mk | mk | homepage | links correct, no dates on the site; homepage order kept |
| mk.bloombergadria.com | mk | homepage | exact times |
| slobodenpecat.mk | mk | blocked | Cloudflare bot check |
| lemonde.fr | fr | RSS | exact times |
| francetvinfo.fr → franceinfo.fr | fr | homepage | exact times |
| lefigaro.fr | fr | homepage | exact times |
| liberation.fr | fr | blocked | DataDome bot check |
| 20minutes.fr | fr | RSS | exact times |
| france24.com/fr | fr | RSS | exact times |
| ouest-france.fr | fr | disallowed | robots.txt: `User-agent: * Disallow: /` |

Forcing the homepage path on the 4 RSS sites also worked. Le Monde got only day precision that way, because its article pages gave no machine-readable time.

## Lightpanda findings

- It's written in Zig, not Rust. Rust is only a build dependency, for the html5ever parser. It ships as a single binary; the nightly tested here was `1.1.0-nightly.12159`.
- It loaded sdk.mk in 3.2 s, against 0.7 s for plain HTTP, with the Cyrillic intact.
- **It doesn't get past bot protection.** Cloudflare and DataDome both blocked it (`err=BotChallenge`). It refuses any user agent containing "Mozilla", by design.
- Useful options: `fetch --dump html|markdown|structured_data`, `--obey-robots`, `--wait-ms`, plus `serve` for control through the Chrome DevTools Protocol (CDP).
- None of the 11 test sites needed it. It stays as the fallback for pages built with JavaScript.

## Limits

- The article-link rules are heuristics. A site with short slugs and no IDs in its URLs falls back to the weaker 4-word rule.
- A site with no date metadata (24.mk) keeps homepage order, which is close to latest-first but not guaranteed.
- No article text is extracted yet. That's the next step.

## Sources

- Lightpanda, a Zig headless browser: https://lilting.ch/en/articles/lightpanda-zig-headless-browser-ai-scraping
- Lightpanda 1.0 release: https://linuxiac.com/lightpanda-1-0-released-as-lightweight-headless-browser-exits-beta/
- Ouest-France robots.txt: https://www.ouest-france.fr/robots.txt
