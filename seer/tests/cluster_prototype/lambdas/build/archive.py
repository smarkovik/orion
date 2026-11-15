"""Per-run archive: articles inserted or changed (full text) and stories created, changed or closed."""

from datetime import datetime

from model import Article, Story, archive_key
from seer_common import store


def write_archive(
    edition: str,
    run_id: str,
    started: datetime,
    articles: list[Article],
    stories: list[Story],
    full_bodies: dict[str, str] | None = None,
    closed_ids: set[str] | None = None,
) -> tuple[str | None, int]:
    if not articles and not stories:
        return None, 0
    writer = store.JsonlGzWriter()
    for a in articles:
        rec = a.to_json()
        rec.pop("vector")
        rec["body"] = (full_bodies or {}).get(a.url, a.body)
        writer.add({"kind": "article", **rec})
    for s in stories:
        writer.add({"kind": "story", **s.to_json(), "state": "closed" if s.id in (closed_ids or set()) else "open"})
    key = archive_key(edition, started, run_id)
    _, _, size = writer.upload(store.RAW_BUCKET, key)
    return key, size
