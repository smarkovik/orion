# Seer

News clustering site inspired by [TIME.mk](https://time.mk).

Status: research and a working prototype (scrape, cluster, public site, admin, AWS deploy via OpenTofu). v0 plan: https://claude.ai/artifact/R8G6t1iVaTFxkMmi7ZsgwQ

Start with [AGENTS.md](AGENTS.md): the project, its layout, conventions and findings in one place.

- `docs/`: research write-ups ([tokenizers](docs/tokenizer-research.md), [TIME.mk sources](docs/timemk-sources.md), [outlet websites and RSS](docs/sources.md), [latest-news scraper](docs/scraper-research.md), [cluster prototype](docs/cluster-prototype-findings.md), [adding a source or a country](docs/adding-sources-and-editions.md))
- `tests/cluster_prototype/`: the prototype: two Lambda images and S3, no database ([README](tests/cluster_prototype/README.md), [Lambda contract](tests/cluster_prototype/lambdas/README.md))
- `tests/`: the other prototypes behind the research
- `infra/tofu/`: OpenTofu for the AWS staging and production accounts ([README](infra/tofu/README.md))

Standalone Postgres + pgvector smoke test (Docker; not used by the prototype):

```bash
tests/postgres/setup.sh up      # prints the DSN; `down` removes the container
pip install -r tests/postgres/requirements.txt
pytest                          # run from seer/
```

Latest news from any site (Lightpanda optional, via `LIGHTPANDA_BIN`):

```bash
pip install -r tests/scraper/requirements.txt
python tests/scraper/latest_news.py https://sdk.mk https://www.lemonde.fr --limit 10
```
