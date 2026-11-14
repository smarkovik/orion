import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

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
MODE = os.environ.get("MODE", "runs")
STORY_THRESHOLD = float(os.environ.get("STORY_THRESHOLD", "0.92"))
STORY_OPEN_HOURS = int(os.environ.get("STORY_OPEN_HOURS", "48"))
STORY_MAX_GAP_HOURS = float(os.environ.get("STORY_MAX_GAP_HOURS", "18"))
STORY_MAX_SPAN_HOURS = float(os.environ.get("STORY_MAX_SPAN_HOURS", "24"))
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


@dataclass
class Art:
    id: int
    source_id: int
    published: datetime
    changed: datetime | None
    domain: str
    cats: list[str]
    vec: np.ndarray
    title: str = ""


@dataclass
class Story:
    id: int | None
    idx: int
    members: list[int] = field(default_factory=list)
    vsum: np.ndarray | None = None
    first_pub: datetime | None = None
    last_pub: datetime | None = None
    created_at: datetime | None = None
    size: int = 0
    updated_at: datetime | None = None
    is_new: bool = False
    gained: bool = False
    dirty: bool = False
    updated: bool = False
    changed_to: datetime | None = None


OPEN_STORIES_SQL = """
SELECT id, size, created_at, updated_at FROM stories
WHERE edition = %(edition)s AND model = %(model)s AND abs(threshold - %(tau)s) < 1e-6 AND state = 'open'
ORDER BY id
"""

MEMBERS_SQL = """
SELECT sa.story_id, a.id, a.source_id, a.published_at, a.content_changed_at, s.domain, a.source_categories,
       e.vector, a.title
FROM story_articles sa
JOIN stories st ON st.id = sa.story_id
JOIN articles a ON a.id = sa.article_id
JOIN sources s ON s.id = a.source_id
JOIN embeddings e ON e.article_id = a.id AND e.model = %(model)s
WHERE st.edition = %(edition)s AND st.model = %(model)s AND abs(st.threshold - %(tau)s) < 1e-6 AND st.state = 'open'
"""

UNASSIGNED_SQL = """
SELECT 0, a.id, a.source_id, a.published_at, a.content_changed_at, s.domain, a.source_categories, e.vector, a.title
FROM articles a
JOIN sources s ON s.id = a.source_id AND s.language = %(edition)s
JOIN embeddings e ON e.article_id = a.id AND e.model = %(model)s AND e.content_hash = a.content_hash
WHERE a.published_at >= now() - make_interval(hours => %(hours)s)
  AND NOT EXISTS (SELECT 1 FROM story_articles sa WHERE sa.article_id = a.id)
ORDER BY a.published_at, a.id
"""

STORY_UPDATE_SQL = """
UPDATE stories SET centroid = %(centroid)s, label_article_id = %(label)s, size = %(size)s,
    source_count = %(sources)s, first_published = %(first)s, last_published = %(last)s,
    region = %(region)s, region_votes = %(region_votes)s, subject = %(subject)s, subject_votes = %(subject_votes)s,
    updated_at = coalesce(%(upd)s, updated_at),
    last_activity_at = greatest(%(last)s, coalesce(%(upd)s, updated_at))
WHERE id = %(id)s
"""

RESCORE_SQL = """
UPDATE stories SET score = ln(1 + source_count)::float8 * power(2::float8, -extract(epoch FROM now() - last_activity_at)
                                                                  / 21600.0)
WHERE edition = %(edition)s AND model = %(model)s AND abs(threshold - %(tau)s) < 1e-6 AND state = 'open'
"""


def art_from_row(r: tuple) -> Art:
    return Art(r[1], r[2], r[3], r[4], r[5], r[6] or [], r[7].to_numpy().astype(np.float32), r[8])


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def run_stories(conn: psycopg.Connection, edition: str, categories: CategoryMap) -> None:
    params = {"edition": edition, "model": MODEL, "tau": STORY_THRESHOLD}
    gap = timedelta(hours=STORY_MAX_GAP_HOURS)
    span = timedelta(hours=STORY_MAX_SPAN_HOURS)
    with conn.transaction():
        closed = conn.execute(
            "UPDATE stories SET state = 'closed' WHERE edition = %(edition)s AND model = %(model)s "
            "AND abs(threshold - %(tau)s) < 1e-6 AND state = 'open' "
            "AND last_published < now() - make_interval(hours => %(hours)s)",
            {**params, "hours": STORY_OPEN_HOURS},
        ).rowcount
        arts: dict[int, Art] = {}
        stories: dict[int, Story] = {}
        rows = conn.execute(OPEN_STORIES_SQL, params).fetchall()
        unassigned = [art_from_row(r) for r in conn.execute(UNASSIGNED_SQL, {**params, "hours": WINDOW_HOURS})]
        cap = len(rows) + len(unassigned)
        sums = np.zeros((cap, 768), dtype=np.float32)
        counts = np.ones(cap, dtype=np.float32)
        first_pubs = np.zeros(cap)
        last_pubs = np.zeros(cap)
        by_idx: list[Story] = []
        for sid, size, created, upd in rows:
            st = Story(sid, len(by_idx), size=size, created_at=created, updated_at=upd)
            stories[sid] = st
            by_idx.append(st)
        for r in conn.execute(MEMBERS_SQL, params).fetchall():
            a = art_from_row(r)
            arts[a.id] = a
            st = stories[r[0]]
            st.members.append(a.id)
            st.vsum = a.vec.copy() if st.vsum is None else st.vsum + a.vec
        empty = [sid for sid, st in stories.items() if not st.members]
        if empty:
            conn.execute("DELETE FROM stories WHERE id = ANY(%s)", (empty,))
        by_idx = [st for st in by_idx if st.members]
        stories = {sid: st for sid, st in stories.items() if st.members}
        for i, st in enumerate(by_idx):
            st.idx = i
            st.dirty = len(st.members) != st.size
            st.first_pub = min(arts[m].published for m in st.members)
            st.last_pub = max(arts[m].published for m in st.members)
            sums[i], counts[i] = st.vsum, len(st.members)
            first_pubs[i], last_pubs[i] = st.first_pub.timestamp(), st.last_pub.timestamp()

        joined = 0
        for a in unassigned:
            arts[a.id] = a
            n = len(by_idx)
            ts = a.published.timestamp()
            best, best_sim = None, -1.0
            if n:
                sims = sums[:n] @ a.vec / counts[:n]
                sims[np.abs(last_pubs[:n] - ts) > gap.total_seconds()] = -1.0
                sims[np.abs(first_pubs[:n] - ts) > span.total_seconds()] = -1.0
                j = int(np.argmax(sims))
                best, best_sim = by_idx[j], float(sims[j])
            if best is not None and best_sim >= STORY_THRESHOLD:
                best.vsum = best.vsum + a.vec
                joined += 1
            else:
                best = Story(None, n, is_new=True, vsum=a.vec.copy(), first_pub=a.published, last_pub=a.published)
                by_idx.append(best)
            best.members.append(a.id)
            best.gained = True
            best.first_pub = min(best.first_pub, a.published)
            if a.published > best.last_pub:
                best.last_pub = a.published
            sums[best.idx], counts[best.idx] = best.vsum, len(best.members)
            first_pubs[best.idx] = best.first_pub.timestamp()
            last_pubs[best.idx] = best.last_pub.timestamp()
        new_count = sum(st.is_new for st in by_idx)

        for st in by_idx:
            changed = [arts[m].changed for m in st.members if arts[m].changed]
            if changed and not st.is_new and max(changed) > max(st.created_at, st.updated_at or st.created_at):
                st.updated, st.changed_to = True, max(changed)
        facets = {aid: categories.facets(a.domain, a.cats) for aid, a in arts.items()}
        touched = [st for st in by_idx if st.gained or st.updated or st.dirty]
        with conn.cursor() as cur:
            for st in touched:
                if st.id is None:
                    st.id = cur.execute(
                        "INSERT INTO stories (edition, model, threshold) VALUES (%(edition)s, %(model)s, %(tau)s) "
                        "RETURNING id",
                        params,
                    ).fetchone()[0]
                members = [arts[m] for m in st.members]
                centroid = unit(np.mean([a.vec for a in members], axis=0))
                sims = [float(a.vec @ centroid) for a in members]
                scored = [(a.id, s) for a, s in zip(members, sims)]
                region, region_votes = vote(scored, facets, "region")
                subject, subject_votes = vote(scored, facets, "subject")
                times = [a.published for a in members]
                cur.execute(
                    STORY_UPDATE_SQL,
                    {
                        "id": st.id,
                        "centroid": centroid,
                        "label": members[int(np.argmax(sims))].id,
                        "size": len(members),
                        "sources": len({a.source_id for a in members}),
                        "first": min(times),
                        "last": max(times),
                        "region": region,
                        "region_votes": region_votes,
                        "subject": subject,
                        "subject_votes": subject_votes,
                        "upd": st.changed_to,
                    },
                )
                cur.executemany(
                    "INSERT INTO story_articles (story_id, article_id, similarity) VALUES (%s, %s, %s) "
                    "ON CONFLICT (article_id) DO UPDATE SET similarity = EXCLUDED.similarity",
                    [(st.id, aid, s) for aid, s in scored],
                )
        conn.execute(RESCORE_SQL, params)
        top = conn.execute(
            "SELECT a.title, st.size, st.source_count, st.region, st.subject, st.score, st.id FROM stories st "
            "JOIN articles a ON a.id = st.label_article_id WHERE st.edition = %(edition)s AND st.model = %(model)s "
            "AND abs(st.threshold - %(tau)s) < 1e-6 AND st.state = 'open' ORDER BY st.score DESC, st.id LIMIT 5",
            params,
        ).fetchall()
        counts = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE source_count >= 2) FROM stories WHERE edition = %(edition)s "
            "AND model = %(model)s AND abs(threshold - %(tau)s) < 1e-6 AND state = 'open'",
            params,
        ).fetchone()
    flags = {st.id: [f for f, on in (("new", st.is_new), ("updated", st.updated)) if on] for st in by_idx}
    print(
        f"\n[{edition}] tau={STORY_THRESHOLD}: unassigned={len(unassigned)} joined={joined} new={new_count} "
        f"updated={sum(st.updated for st in by_idx)} closed={closed} open={counts[0]} multi_source={counts[1]}"
    )
    for title, size, sources, region, subject, score, sid in top:
        tags = ",".join(flags.get(sid) or []) or "-"
        print(
            f"  [{size} articles / {sources} sources, {region or '-'} / {subject or '-'}, score {score:.2f}, {tags}] "
            f"{title}"
        )


def run_batch(conn: psycopg.Connection, cfg: dict) -> None:
    by_edition: dict[str, list] = {}
    for row in conn.execute(WINDOW_SQL, {"model": MODEL, "hours": WINDOW_HOURS}).fetchall():
        by_edition.setdefault(row[7], []).append(row)
    for edition in sorted(by_edition):
        if EDITION and edition != EDITION:
            continue
        categories = CategoryMap(cfg, edition)
        for threshold in THRESHOLDS:
            run_threshold(conn, edition, threshold, by_edition[edition], categories)


def main() -> None:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        register_vector(conn)
        embed_pending(conn)
        if MODE == "stories":
            for (edition,) in conn.execute("SELECT DISTINCT language FROM sources ORDER BY 1").fetchall():
                if not EDITION or edition == EDITION:
                    run_stories(conn, edition, CategoryMap(cfg, edition))
        else:
            run_batch(conn, cfg)


if __name__ == "__main__":
    main()
