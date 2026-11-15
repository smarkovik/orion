# Seer

News clustering site inspired by [TIME.mk](https://time.mk).

Status: research and a working prototype (scrape, cluster, public site, admin, AWS deploy via OpenTofu). v0 plan: https://claude.ai/artifact/R8G6t1iVaTFxkMmi7ZsgwQ

Staging (sandbox account, not indexed by search engines):

- Site: https://dx6a9ps6mjps1.cloudfront.net
- Admin: https://dx6a9ps6mjps1.cloudfront.net/system/admin/

The hourly schedule is off. Fetch on demand (the build runs by itself when a scrape finishes):

```bash
for e in mk fr; do
  aws lambda invoke --function-name seer-staging-scrape --invocation-type Event \
    --cli-binary-format raw-in-base64-out --payload "{\"edition\":\"$e\"}" /dev/null
done
```

### Sync button and Lambda cost (admin)

The admin page has a "Sync and Lambda cost" block: **Sync now** starts a scrape of both editions (the build follows by
itself), and the block shows what the Lambdas cost, read from their CloudWatch logs (billed time × memory, failed and
timed-out invocations included; logs are kept 14 days). The "Latest runs" table gets a "Lambda (logs)" column.

**Temporary token** (staging only, until the admin has real authentication):

```text
alB39UF_chhcD_xifH5GieATV_-HH9Kusq2BDeqiKtA
```

1. Open the admin page, click **Token**, paste it. It is kept in your browser only.
2. Click **Sync now**. Wait about two minutes; the page reloads the data by itself.

Limits, enforced by the function: at most one sync every 15 minutes (any scrape start counts, also from the CLI) and
48 scrape starts per 24 hours (24 syncs).

**This repository is public, so this token is public.** Anyone with it can start syncs within those limits and read the
cost numbers; nothing else. Replace it with real authentication before this is more than a sandbox. To rotate it:

```bash
python3 -c "import secrets,hashlib; t=secrets.token_urlsafe(32); print(t); print(hashlib.sha256(t.encode()).hexdigest())"
```

Put the second line in `control_token_sha256` in `infra/tofu/envs/staging/terraform.tfvars` and the first line here,
then deploy (merge to `main` with deploys on, or `tofu apply` in `infra/tofu/envs/staging`). Setting
`control_token_sha256 = ""` removes the function and the `/system/control/` route.

From a shell, with the token in `$T`:

```bash
curl -s -H "x-seer-token: $T" -X POST https://dx6a9ps6mjps1.cloudfront.net/system/control/sync
curl -s -H "x-seer-token: $T" "https://dx6a9ps6mjps1.cloudfront.net/system/control/cost?days=7"
```

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
