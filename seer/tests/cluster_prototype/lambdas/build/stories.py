"""Embedding and story assignment on the in-memory window (port of clusterer/cluster.py run_stories)."""

import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from categories import CategoryMap, vote
from model import DIM, Article, Story, Window

MODEL = os.environ.get("MODEL", "intfloat/multilingual-e5-base")
MODEL_PATH = os.environ.get("MODEL_PATH") or None
WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "48"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "32"))
MAX_CHARS = 1200
STORY_THRESHOLD = float(os.environ.get("STORY_THRESHOLD", "0.92"))
STORY_OPEN_HOURS = int(os.environ.get("STORY_OPEN_HOURS", "48"))
STORY_MAX_GAP_HOURS = float(os.environ.get("STORY_MAX_GAP_HOURS", "18"))
STORY_MAX_SPAN_HOURS = float(os.environ.get("STORY_MAX_SPAN_HOURS", "24"))

_model: Any = None


def get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_PATH or MODEL, device="cpu")
    return _model


def embed_new(window: Window) -> tuple[int, float]:
    """Embed articles without a vector. Returns (count, seconds)."""
    pending = sorted((a for a in window.articles.values() if a.vector is None), key=lambda a: a.url)
    if not pending:
        return 0, 0.0
    model = get_model()
    texts = [f"query: {a.title}. {(a.body or '')[:MAX_CHARS]}" for a in pending]
    start = time.perf_counter()
    vectors = model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
    elapsed = time.perf_counter() - start
    for a, v in zip(pending, vectors):
        a.vector = np.asarray(v, dtype=np.float32)
    return len(pending), elapsed


@dataclass
class _St:
    idx: int
    story: Story | None
    members: list[Article] = field(default_factory=list)
    vsum: np.ndarray | None = None
    first_pub: datetime | None = None
    last_pub: datetime | None = None
    is_new: bool = False
    gained: bool = False
    dirty: bool = False
    updated: bool = False
    changed_to: datetime | None = None


def assign(window: Window, categories: CategoryMap, now: datetime) -> tuple[dict[str, int], set[str], list[Story]]:
    gap = timedelta(hours=STORY_MAX_GAP_HOURS).total_seconds()
    span = timedelta(hours=STORY_MAX_SPAN_HOURS).total_seconds()

    cutoff = now - timedelta(hours=STORY_OPEN_HOURS)
    closed = [s for s in window.stories.values() if s.last_published < cutoff]
    for s in closed:
        del window.stories[s.id]

    by_idx: list[_St] = []
    for s in sorted(window.stories.values(), key=lambda s: s.id):
        members = [
            window.articles[u] for u in s.members if u in window.articles and window.articles[u].vector is not None
        ]
        if not members:
            del window.stories[s.id]
            continue
        st = _St(len(by_idx), s, members, np.sum([a.vector for a in members], axis=0))
        st.dirty = len(members) != s.size
        st.first_pub = min(a.published_at for a in members)
        st.last_pub = max(a.published_at for a in members)
        by_idx.append(st)

    horizon = now - timedelta(hours=WINDOW_HOURS)
    unassigned = sorted(
        (
            a
            for a in window.articles.values()
            if a.vector is not None and a.story_id is None and a.published_at >= horizon
        ),
        key=lambda a: (a.published_at, a.url),
    )
    cap = len(by_idx) + len(unassigned)
    sums = np.zeros((cap, DIM), dtype=np.float32)
    counts = np.ones(cap, dtype=np.float32)
    first_pubs = np.zeros(cap)
    last_pubs = np.zeros(cap)
    for st in by_idx:
        sums[st.idx], counts[st.idx] = st.vsum, len(st.members)
        first_pubs[st.idx] = st.first_pub.timestamp()  # type: ignore[union-attr]
        last_pubs[st.idx] = st.last_pub.timestamp()  # type: ignore[union-attr]

    joined = 0
    for a in unassigned:
        n = len(by_idx)
        ts = a.published_at.timestamp()
        best: _St | None = None
        best_sim = -1.0
        if n:
            sims = sums[:n] @ a.vector / counts[:n]
            sims[np.abs(last_pubs[:n] - ts) > gap] = -1.0
            sims[np.abs(first_pubs[:n] - ts) > span] = -1.0
            j = int(np.argmax(sims))
            best, best_sim = by_idx[j], float(sims[j])
        if best is not None and best_sim >= STORY_THRESHOLD:
            best.vsum = best.vsum + a.vector
            joined += 1
        else:
            best = _St(n, None, vsum=a.vector.copy(), first_pub=a.published_at, last_pub=a.published_at, is_new=True)
            by_idx.append(best)
        best.members.append(a)
        best.gained = True
        best.first_pub = min(best.first_pub, a.published_at)  # type: ignore[type-var]
        if a.published_at > best.last_pub:  # type: ignore[operator]
            best.last_pub = a.published_at
        sums[best.idx], counts[best.idx] = best.vsum, len(best.members)
        first_pubs[best.idx] = best.first_pub.timestamp()  # type: ignore[union-attr]
        last_pubs[best.idx] = best.last_pub.timestamp()  # type: ignore[union-attr]

    for st in by_idx:
        if st.story is None:
            continue
        changed = [a.content_changed_at for a in st.members if a.content_changed_at]
        base = max(st.story.created_at, st.story.updated_at or st.story.created_at)
        if changed and max(changed) > base:
            st.updated, st.changed_to = True, max(changed)

    touched: set[str] = set()
    for st in by_idx:
        if not (st.gained or st.updated or st.dirty):
            continue
        s = st.story
        if s is None:
            s = Story(
                id=window.new_story_id(),
                created_at=now,
                last_activity_at=now,
                first_published=st.first_pub,  # type: ignore[arg-type]
                last_published=st.last_pub,  # type: ignore[arg-type]
            )
            window.stories[s.id] = s
            st.story = s
        centroid = st.vsum / np.linalg.norm(st.vsum)  # type: ignore[operator]
        sims = [float(a.vector @ centroid) for a in st.members]
        order = sorted(range(len(st.members)), key=lambda i: (-sims[i], st.members[i].url))
        scored = [(st.members[i].url, sims[i]) for i in order]
        facets = {a.url: categories.facets(a.source, a.source_categories) for a in st.members}
        s.region, s.region_votes = vote(scored, facets, "region")  # type: ignore[arg-type]
        s.subject, s.subject_votes = vote(scored, facets, "subject")  # type: ignore[arg-type]
        s.members = [u for u, _ in scored]
        s.label_url = st.members[int(np.argmax(sims))].url
        s.size = len(st.members)
        s.source_count = len({a.source for a in st.members})
        s.first_published = min(a.published_at for a in st.members)
        s.last_published = max(a.published_at for a in st.members)
        if st.changed_to:
            s.updated_at = st.changed_to
        s.last_activity_at = max(s.last_published, s.updated_at) if s.updated_at else s.last_published
        for a in st.members:
            a.story_id = s.id
        touched.add(s.id)

    for s in window.stories.values():
        hours = (now - s.last_activity_at).total_seconds() / 3600
        s.score = math.log(1 + s.source_count) * 2 ** (-hours / 6)

    result = {
        "unassigned": len(unassigned),
        "joined": joined,
        "new": sum(st.is_new for st in by_idx),
        "updated": sum(st.updated for st in by_idx),
        "closed": len(closed),
        "open": len(window.stories),
        "multi_source": sum(s.source_count >= 2 for s in window.stories.values()),
    }
    return result, touched, closed
