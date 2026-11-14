# Seer

News clustering site inspired by [TIME.mk](https://time.mk).

Status: research, no product code yet. v0 plan: https://claude.ai/artifact/R8G6t1iVaTFxkMmi7ZsgwQ

- `docs/`: research write-ups ([tokenizers](docs/tokenizer-research.md), [TIME.mk sources](docs/timemk-sources.md), [outlet websites and RSS](docs/sources.md))
- `tests/`: prototypes behind the research

Postgres + pgvector (Docker):

```bash
tests/postgres/setup.sh up      # prints the DSN; `down` removes the container
pip install -r tests/postgres/requirements.txt
pytest                          # run from seer/
```
