#!/usr/bin/env python3
"""Compare open stories of the database-free build (S3 window) with the legacy Postgres stories, per edition."""

import gzip
import json
import os
import sys
from collections import Counter
from math import comb
from pathlib import Path

S3_DIR = Path(os.environ.get("S3_DIR", "/s3"))
BUCKET = os.environ.get("RAW_BUCKET", "seer-raw")
EDITIONS = [e for e in os.environ.get("EDITIONS", "mk,fr").split(",") if e]

LEGACY_SQL = """
SELECT sa.story_id, a.url, a.source_id
FROM stories st
JOIN story_articles sa ON sa.story_id = st.id
JOIN articles a ON a.id = sa.article_id
JOIN sources s ON s.id = a.source_id
WHERE st.state = 'open' AND s.language = %s
"""


def load_window(edition: str) -> list[dict]:
    path = S3_DIR / BUCKET / "state" / edition / "window.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)["stories"]


def load_legacy(conn, edition: str) -> tuple[dict[str, str], dict[str, int]]:
    """URL -> story id, and story id -> distinct source count."""
    labels: dict[str, str] = {}
    sources: dict[str, set] = {}
    for story_id, url, source_id in conn.execute(LEGACY_SQL, (edition,)):
        labels[url] = str(story_id)
        sources.setdefault(str(story_id), set()).add(source_id)
    return labels, {k: len(v) for k, v in sources.items()}


def stats(labels: dict[str, str], source_counts: dict[str, int]) -> dict[str, int]:
    sizes = Counter(labels.values())
    return {
        "open": len(sizes),
        "multi": sum(1 for s in sizes if source_counts.get(s, 0) >= 2),
        "largest": max(sizes.values(), default=0),
        "articles": len(labels),
    }


def agreement(a: dict[str, str], b: dict[str, str]) -> dict[str, float | int | None]:
    """Pairs of shared articles that are together in A, in B, and in both; agreement = both / (A or B)."""
    common = a.keys() & b.keys()
    in_a = Counter(a[u] for u in common)
    in_b = Counter(b[u] for u in common)
    both = Counter((a[u], b[u]) for u in common)
    pa = sum(comb(n, 2) for n in in_a.values())
    pb = sum(comb(n, 2) for n in in_b.values())
    pab = sum(comb(n, 2) for n in both.values())
    union = pa + pb - pab
    return {
        "common": len(common),
        "pairs_a": pa,
        "pairs_b": pb,
        "pairs_both": pab,
        "agreement": pab / union if union else None,
    }


def table(rows: list[list]) -> str:
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(str(c).rjust(w) if i else str(c).ljust(w) for i, (c, w) in enumerate(zip(r, widths))) for r in rows
    )


def compare(conn, edition: str) -> str:
    stories = load_window(edition)
    win = {url: s["id"] for s in stories for url in s["members"]}
    win_src = {s["id"]: s.get("source_count", 0) for s in stories}
    leg, leg_src = load_legacy(conn, edition)
    sw, sl = stats(win, win_src), stats(leg, leg_src)
    ag = agreement(win, leg)
    rows = [["", "open stories", "2+ sources", "largest", "articles"]]
    rows.append(["s3 (no db)"] + [sw[k] for k in ("open", "multi", "largest", "articles")])
    rows.append(["postgres"] + [sl[k] for k in ("open", "multi", "largest", "articles")])
    pct = "n/a" if ag["agreement"] is None else f"{ag['agreement']:.1%}"
    lines = [
        f"== {edition}",
        table(rows),
        f"articles in both: {ag['common']}",
        f"pairs together: s3 {ag['pairs_a']}, postgres {ag['pairs_b']}, both {ag['pairs_both']}",
        f"co-assignment agreement: {pct}",
    ]
    return "\n".join(lines)


def main() -> int:
    import psycopg

    failed = False
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for edition in EDITIONS:
            try:
                print(compare(conn, edition), end="\n\n")
            except FileNotFoundError as e:
                failed = True
                print(f"== {edition}\nno window: {e.filename}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
