import math
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import psycopg
import yaml
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

DATABASE_URL = os.environ["DATABASE_URL"]
MODEL = os.environ.get("MODEL", "intfloat/multilingual-e5-base")
THRESHOLDS = [float(t) for t in os.environ.get("THRESHOLDS", "0.82,0.86,0.90").split(",")]
WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "48"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "32"))
MAX_CHARS = int(os.environ.get("MAX_CHARS", "1200"))
CATEGORIES_FILE = os.environ.get("CATEGORIES_FILE", "/app/categories.yaml")
EDITION = os.environ.get("EDITION", "")
METHOD = "hac-average"
PREFIX = "query: " if "e5" in MODEL.lower() else ""

PENDING_SQL = """
SELECT a.id, a.title, a.body, a.content_hash
FROM articles a
LEFT JOIN embeddings e ON e.article_id = a.id AND e.model = %(model)s
WHERE a.published_at >= now() - make_interval(hours => %(hours)s)
  AND (e.article_id IS NULL OR e.content_hash <> a.content_hash)
ORDER BY a.id
"""

UPSERT_SQL = """
INSERT INTO embeddings (article_id, model, content_hash, vector)
VALUES (%s, %s, %s, %s)
ON CONFLICT (article_id, model) DO UPDATE
SET content_hash = EXCLUDED.content_hash, vector = EXCLUDED.vector, created_at = now()
"""

WINDOW_SQL = """
SELECT a.id, a.source_id, a.published_at, a.title, e.vector, s.domain, a.source_categories, s.language
FROM articles a
JOIN sources s ON s.id = a.source_id
JOIN embeddings e ON e.article_id = a.id AND e.model = %(model)s AND e.content_hash = a.content_hash
WHERE a.published_at >= now() - make_interval(hours => %(hours)s)
ORDER BY a.id
"""


class CategoryMap:
    """Static mapping of source category names to our region and subject."""

    def __init__(self, cfg: dict, edition: str) -> None:
        rules = ((cfg.get("editions") or {}).get(edition) or {}).get("rules") or {}
        self.rules = {
            facet: [(value, re.compile(p)) for value, patterns in (values or {}).items() for p in patterns]
            for facet, values in rules.items()
        }
        self.domains: dict[str, dict] = cfg.get("domains") or {}

    def facets(self, domain: str, names: list[str]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {facet: set() for facet in ("region", "subject")}
        overrides = self.domains.get(domain) or {}
        for name in names:
            if name in overrides:
                for facet, value in (overrides[name] or {}).items():
                    out[facet].add(value)
                continue
            low = name.strip().lower()
            for facet, rules in self.rules.items():
                match = next((value for value, pattern in rules if pattern.search(low)), None)
                if match:
                    out[facet].add(match)
        return out


def vote(
    members: list[tuple[int, float]], facets: dict[int, dict[str, set[str]]], facet: str
) -> tuple[str | None, int]:
    counts = Counter(v for aid, _ in members for v in facets[aid][facet])
    if not counts:
        return None, 0
    best = max(counts.values())
    tied = {v for v, n in counts.items() if n == best}
    # Ties go to the member closest to the centroid.
    for aid, _ in sorted(members, key=lambda m: -m[1]):
        hit = tied & facets[aid][facet]
        if hit:
            return min(hit), best
    return None, 0


def embed_pending(conn: psycopg.Connection) -> None:
    rows = conn.execute(PENDING_SQL, {"model": MODEL, "hours": WINDOW_HOURS}).fetchall()
    print(f"embedding: {len(rows)} articles to embed")
    if not rows:
        return
    model = SentenceTransformer(MODEL, device="cpu")
    texts = [f"{PREFIX}{title}. {(body or '')[:MAX_CHARS]}" for _, title, body, _ in rows]
    start = time.perf_counter()
    vectors = model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
    elapsed = time.perf_counter() - start
    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, [(r[0], MODEL, r[3], v) for r, v in zip(rows, vectors)])
    print(f"embedding time: {elapsed:.1f}s ({len(rows) / elapsed:.1f} articles/s)")


def cluster_labels(vectors: np.ndarray, threshold: float) -> np.ndarray:
    if len(vectors) < 2:
        return np.zeros(len(vectors), dtype=int)
    model = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=1 - threshold
    )
    return model.fit_predict(vectors)


def build_clusters(
    labels: np.ndarray, vectors: np.ndarray, ids: list[int], sources: list[int], published: list[datetime]
) -> list[dict]:
    now = datetime.now(timezone.utc)
    clusters = []
    for label in np.unique(labels):
        idx = np.flatnonzero(labels == label)
        centroid = vectors[idx].mean(axis=0)
        centroid /= np.linalg.norm(centroid)
        sims = vectors[idx] @ centroid
        times = [published[i] for i in idx]
        last = max(times)
        source_count = len({sources[i] for i in idx})
        hours = (now - last).total_seconds() / 3600
        clusters.append(
            {
                "label_article_id": ids[idx[int(np.argmax(sims))]],
                "size": len(idx),
                "source_count": source_count,
                "first_published": min(times),
                "last_published": last,
                "score": math.log(1 + source_count) * 2 ** (-hours / 6),
                "members": [(ids[i], float(s)) for i, s in zip(idx, sims)],
            }
        )
    return clusters


def save_run(
    conn: psycopg.Connection, edition: str, threshold: float, article_count: int, clusters: list[dict]
) -> None:
    with conn.transaction():
        run_id = conn.execute(
            """
            INSERT INTO cluster_runs (model, method, threshold, window_hours, article_count, cluster_count,
                                      multi_source_count, largest_cluster, edition)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                MODEL,
                METHOD,
                threshold,
                WINDOW_HOURS,
                article_count,
                len(clusters),
                sum(c["source_count"] >= 2 for c in clusters),
                max((c["size"] for c in clusters), default=0),
                edition,
            ),
        ).fetchone()[0]
        with conn.cursor() as cur:
            for c in clusters:
                cluster_id = cur.execute(
                    """
                    INSERT INTO clusters (run_id, label_article_id, size, source_count, first_published,
                                          last_published, score, region, region_votes, subject, subject_votes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        run_id,
                        c["label_article_id"],
                        c["size"],
                        c["source_count"],
                        c["first_published"],
                        c["last_published"],
                        c["score"],
                        c["region"],
                        c["region_votes"],
                        c["subject"],
                        c["subject_votes"],
                    ),
                ).fetchone()[0]
                cur.executemany(
                    "INSERT INTO cluster_articles (cluster_id, article_id, similarity) VALUES (%s, %s, %s)",
                    [(cluster_id, aid, sim) for aid, sim in c["members"]],
                )


def run_threshold(
    conn: psycopg.Connection, edition: str, threshold: float, rows: list, categories: CategoryMap
) -> None:
    ids = [r[0] for r in rows]
    sources = [r[1] for r in rows]
    published = [r[2] for r in rows]
    titles = {r[0]: r[3] for r in rows}
    vectors = np.array([r[4].to_numpy() for r in rows], dtype=np.float32).reshape(len(rows), -1)
    clusters = build_clusters(cluster_labels(vectors, threshold), vectors, ids, sources, published) if rows else []
    facets = {r[0]: categories.facets(r[5], r[6] or []) for r in rows}
    for c in clusters:
        c["region"], c["region_votes"] = vote(c["members"], facets, "region")
        c["subject"], c["subject_votes"] = vote(c["members"], facets, "subject")
    save_run(conn, edition, threshold, len(rows), clusters)
    multi = sorted((c for c in clusters if c["source_count"] >= 2), key=lambda c: c["score"], reverse=True)
    print(
        f"\n[{edition}] tau={threshold}: articles={len(rows)} clusters={len(clusters)} multi_source={len(multi)} "
        f"largest={max((c['size'] for c in clusters), default=0)}"
    )
    if multi:
        with_region = sum(c["region"] is not None for c in multi) / len(multi)
        with_subject = sum(c["subject"] is not None for c in multi) / len(multi)
        print(f"  categories on multi-source clusters: region {with_region:.0%}, subject {with_subject:.0%}")
    for c in multi[:5]:
        print(
            f"  [{c['size']} articles / {c['source_count']} sources, {c['region'] or '-'} / {c['subject'] or '-'}, "
            f"score {c['score']:.2f}] {titles[c['label_article_id']]}"
        )


def main() -> None:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        register_vector(conn)
        embed_pending(conn)
        by_edition: dict[str, list] = {}
        for row in conn.execute(WINDOW_SQL, {"model": MODEL, "hours": WINDOW_HOURS}).fetchall():
            by_edition.setdefault(row[7], []).append(row)
        for edition in sorted(by_edition):
            if EDITION and edition != EDITION:
                continue
            categories = CategoryMap(cfg, edition)
            for threshold in THRESHOLDS:
                run_threshold(conn, edition, threshold, by_edition[edition], categories)


if __name__ == "__main__":
    main()
