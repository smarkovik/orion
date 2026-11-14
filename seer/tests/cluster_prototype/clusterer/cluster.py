import math
import os
import time
from datetime import datetime, timezone

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

DATABASE_URL = os.environ["DATABASE_URL"]
MODEL = os.environ.get("MODEL", "intfloat/multilingual-e5-base")
THRESHOLDS = [float(t) for t in os.environ.get("THRESHOLDS", "0.82,0.86,0.90").split(",")]
WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "48"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "32"))
MAX_CHARS = int(os.environ.get("MAX_CHARS", "1200"))
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
SELECT a.id, a.source_id, a.published_at, a.title, e.vector
FROM articles a
JOIN embeddings e ON e.article_id = a.id AND e.model = %(model)s AND e.content_hash = a.content_hash
WHERE a.published_at >= now() - make_interval(hours => %(hours)s)
ORDER BY a.id
"""


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


def save_run(conn: psycopg.Connection, threshold: float, article_count: int, clusters: list[dict]) -> None:
    with conn.transaction():
        run_id = conn.execute(
            """
            INSERT INTO cluster_runs (model, method, threshold, window_hours, article_count, cluster_count,
                                      multi_source_count, largest_cluster)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
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
            ),
        ).fetchone()[0]
        with conn.cursor() as cur:
            for c in clusters:
                cluster_id = cur.execute(
                    """
                    INSERT INTO clusters (run_id, label_article_id, size, source_count, first_published,
                                          last_published, score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        run_id,
                        c["label_article_id"],
                        c["size"],
                        c["source_count"],
                        c["first_published"],
                        c["last_published"],
                        c["score"],
                    ),
                ).fetchone()[0]
                cur.executemany(
                    "INSERT INTO cluster_articles (cluster_id, article_id, similarity) VALUES (%s, %s, %s)",
                    [(cluster_id, aid, sim) for aid, sim in c["members"]],
                )


def run_threshold(conn: psycopg.Connection, threshold: float, rows: list) -> None:
    ids = [r[0] for r in rows]
    sources = [r[1] for r in rows]
    published = [r[2] for r in rows]
    titles = {r[0]: r[3] for r in rows}
    vectors = np.array([r[4] for r in rows], dtype=np.float32).reshape(len(rows), -1)
    clusters = build_clusters(cluster_labels(vectors, threshold), vectors, ids, sources, published) if rows else []
    save_run(conn, threshold, len(rows), clusters)
    multi = sorted((c for c in clusters if c["source_count"] >= 2), key=lambda c: c["score"], reverse=True)
    print(
        f"\ntau={threshold}: articles={len(rows)} clusters={len(clusters)} multi_source={len(multi)} "
        f"largest={max((c['size'] for c in clusters), default=0)}"
    )
    for c in multi[:5]:
        print(f"  [{c['size']} articles / {c['source_count']} sources, score {c['score']:.2f}] "
              f"{titles[c['label_article_id']]}")


def main() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        register_vector(conn)
        embed_pending(conn)
        rows = conn.execute(WINDOW_SQL, {"model": MODEL, "hours": WINDOW_HOURS}).fetchall()
        for threshold in THRESHOLDS:
            run_threshold(conn, threshold, rows)


if __name__ == "__main__":
    main()
