"""In-memory hot state of one edition (the last ~48 h), stored as one gzipped JSON object in S3."""

import base64
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

BODY_KEEP = 5000  # chars kept for change detection; the archive keeps the full text
DIM = 768


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class Article:
    url: str  # canonical URL; the key
    source: str  # domain
    title: str
    body: str  # first BODY_KEEP chars
    content_hash: str  # sha256 of title + full body
    published_at: datetime
    first_seen_at: datetime
    updated_at: datetime  # last stored change of any kind
    image_url: str | None = None
    source_categories: list[str] = field(default_factory=list)
    source_modified_at: datetime | None = None
    checked_at: datetime | None = None
    content_changed_at: datetime | None = None  # last meaningful change
    change_count: int = 0
    vector: np.ndarray | None = None  # float32 unit vector, set once
    story_id: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "source": self.source,
            "title": self.title,
            "body": self.body,
            "content_hash": self.content_hash,
            "published_at": _iso(self.published_at),
            "first_seen_at": _iso(self.first_seen_at),
            "updated_at": _iso(self.updated_at),
            "image_url": self.image_url,
            "source_categories": self.source_categories,
            "source_modified_at": _iso(self.source_modified_at),
            "checked_at": _iso(self.checked_at),
            "content_changed_at": _iso(self.content_changed_at),
            "change_count": self.change_count,
            "vector": (
                base64.b64encode(self.vector.astype(np.float32).tobytes()).decode() if self.vector is not None else None
            ),
            "story_id": self.story_id,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Article":
        vec = d.get("vector")
        return cls(
            url=d["url"],
            source=d["source"],
            title=d["title"],
            body=d["body"],
            content_hash=d["content_hash"],
            published_at=_dt(d["published_at"]),  # type: ignore[arg-type]
            first_seen_at=_dt(d["first_seen_at"]),  # type: ignore[arg-type]
            updated_at=_dt(d["updated_at"]),  # type: ignore[arg-type]
            image_url=d.get("image_url"),
            source_categories=d.get("source_categories") or [],
            source_modified_at=_dt(d.get("source_modified_at")),
            checked_at=_dt(d.get("checked_at")),
            content_changed_at=_dt(d.get("content_changed_at")),
            change_count=d.get("change_count", 0),
            vector=np.frombuffer(base64.b64decode(vec), dtype=np.float32).copy() if vec else None,
            story_id=d.get("story_id"),
        )


@dataclass
class Story:
    id: str
    created_at: datetime
    last_activity_at: datetime
    first_published: datetime
    last_published: datetime
    members: list[str] = field(default_factory=list)  # article URLs
    label_url: str | None = None
    size: int = 0
    source_count: int = 0
    updated_at: datetime | None = None  # last member edit that bumped the story
    region: str | None = None
    region_votes: int = 0
    subject: str | None = None
    subject_votes: int = 0
    score: float = 0.0
    thumb_key: str | None = None  # site bucket key; None = not tried, "" = no usable image
    thumb_src: str | None = None  # image URL the thumbnail came from
    thumb_source: str | None = None  # domain credited for the photo

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": _iso(self.created_at),
            "last_activity_at": _iso(self.last_activity_at),
            "first_published": _iso(self.first_published),
            "last_published": _iso(self.last_published),
            "members": self.members,
            "label_url": self.label_url,
            "size": self.size,
            "source_count": self.source_count,
            "updated_at": _iso(self.updated_at),
            "region": self.region,
            "region_votes": self.region_votes,
            "subject": self.subject,
            "subject_votes": self.subject_votes,
            "score": self.score,
            "thumb_key": self.thumb_key,
            "thumb_src": self.thumb_src,
            "thumb_source": self.thumb_source,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Story":
        return cls(
            id=d["id"],
            created_at=_dt(d["created_at"]),  # type: ignore[arg-type]
            last_activity_at=_dt(d["last_activity_at"]),  # type: ignore[arg-type]
            first_published=_dt(d["first_published"]),  # type: ignore[arg-type]
            last_published=_dt(d["last_published"]),  # type: ignore[arg-type]
            members=list(d.get("members") or []),
            label_url=d.get("label_url"),
            size=d.get("size", 0),
            source_count=d.get("source_count", 0),
            updated_at=_dt(d.get("updated_at")),
            region=d.get("region"),
            region_votes=d.get("region_votes", 0),
            subject=d.get("subject"),
            subject_votes=d.get("subject_votes", 0),
            score=d.get("score", 0.0),
            thumb_key=d.get("thumb_key"),
            thumb_src=d.get("thumb_src"),
            thumb_source=d.get("thumb_source"),
        )


@dataclass
class Window:
    """Open stories and the articles of the last WINDOW_HOURS for one edition. Only open stories are kept."""

    edition: str
    articles: dict[str, Article] = field(default_factory=dict)
    stories: dict[str, Story] = field(default_factory=dict)
    last_run_id: str | None = None
    last_run_started_at: datetime | None = None
    source_last_ok: dict[str, datetime] = field(default_factory=dict)  # per source, for scrape's modified_after
    next_story_seq: int = 1

    def new_story_id(self) -> str:
        sid = f"{self.edition}-{self.next_story_seq}"
        self.next_story_seq += 1
        return sid

    def to_json(self) -> dict[str, Any]:
        return {
            "v": 1,
            "edition": self.edition,
            "last_run_id": self.last_run_id,
            "last_run_started_at": _iso(self.last_run_started_at),
            "source_last_ok": {k: _iso(v) for k, v in self.source_last_ok.items()},
            "next_story_seq": self.next_story_seq,
            "articles": [a.to_json() for a in self.articles.values()],
            "stories": [s.to_json() for s in self.stories.values()],
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Window":
        arts = [Article.from_json(a) for a in d.get("articles", [])]
        stories = [Story.from_json(s) for s in d.get("stories", [])]
        return cls(
            edition=d["edition"],
            articles={a.url: a for a in arts},
            stories={s.id: s for s in stories},
            last_run_id=d.get("last_run_id"),
            last_run_started_at=_dt(d.get("last_run_started_at")),
            source_last_ok={k: _dt(v) for k, v in (d.get("source_last_ok") or {}).items() if v},  # type: ignore[misc]
            next_story_seq=d.get("next_story_seq", 1),
        )


def window_key(edition: str) -> str:
    return f"state/{edition}/window.json.gz"


def summary_key(edition: str) -> str:
    return f"state/{edition}/summary.json"


def build_report_key(edition: str, run_id: str) -> str:
    return f"builds/{edition}/{run_id}.json"


def archive_key(edition: str, started: datetime, run_id: str) -> str:
    return f"archive/{edition}/{started:%Y/%m/%d}/{run_id}.jsonl.gz"


def days_key(edition: str) -> str:
    return f"state/{edition}/days.json"
