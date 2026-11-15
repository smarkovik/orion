from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from stories_data import (
    EDITIONS,
    NONE,
    VIEWS,
    edition_name,
    facet_filter,
    load_stories,
    local_dt,
    query,
    safe_url,
    story_editions,
    story_facets,
)

THRESHOLD_TOLERANCE = 0.001 + 1e-6

app = FastAPI(title="Cluster viewer", docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


templates.env.filters["local_dt"] = local_dt
templates.env.filters["safe_url"] = safe_url


def fmt_threshold(value: float) -> str:
    return f"{value:.2f}"


templates.env.filters["edition_name"] = edition_name
templates.env.filters["threshold"] = fmt_threshold


def load_clusters(
    run_id: int, min_sources: int, region: str | None = None, subject: str | None = None
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    region_sql, region_args = facet_filter("region", region)
    subject_sql, subject_args = facet_filter("subject", subject)
    clusters = query(
        f"""
        SELECT c.id, c.size, c.source_count, c.first_published, c.last_published, c.score,
               c.region, c.region_votes, c.subject, c.subject_votes,
               a.title AS label_title, a.url AS label_url
        FROM clusters c JOIN articles a ON a.id = c.label_article_id
        WHERE c.run_id = %s AND c.source_count >= %s{region_sql}{subject_sql}
        ORDER BY c.source_count DESC, c.size DESC, c.score DESC, c.id
        """,
        (run_id, min_sources, *region_args, *subject_args),
    )
    members: dict[int, list[dict[str, Any]]] = {c["id"]: [] for c in clusters}
    if clusters:
        rows = query(
            """
            SELECT ca.cluster_id, ca.similarity, a.title, a.url, a.published_at, a.source_categories,
                   s.name AS source_name
            FROM cluster_articles ca
            JOIN articles a ON a.id = ca.article_id
            JOIN sources s ON s.id = a.source_id
            WHERE ca.cluster_id = ANY(%s)
            ORDER BY ca.cluster_id, ca.similarity DESC, a.id
            """,
            (list(members),),
        )
        for row in rows:
            members[row["cluster_id"]].append(row)
    return clusters, members


def facet_counts(run_id: int, column: str, min_sources: int) -> list[dict[str, Any]]:
    return query(
        f"SELECT coalesce(c.{column}, %s) AS value, count(*) AS n FROM clusters c "
        "WHERE c.run_id = %s AND c.source_count >= %s GROUP BY 1 ORDER BY n DESC, value",
        (NONE, run_id, min_sources),
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request, edition: str | None = Query(None, max_length=20)) -> HTMLResponse:
    runs = query("SELECT * FROM cluster_runs ORDER BY created_at DESC, id DESC")
    codes = edition_codes(runs)
    shown = [r for r in runs if edition is None or r["edition"] == edition]
    latest = next(iter(runs), None)
    ctx = {
        "runs": shown,
        "editions": codes,
        "edition": edition,
        "latest_threshold": latest and latest["threshold"],
        "story_editions": story_editions(),
    }
    return templates.TemplateResponse(request, "index.html", ctx)


def edition_codes(runs: list[dict[str, Any]]) -> list[str]:
    extra = sorted({r["edition"] for r in runs} - set(EDITIONS))
    return [*EDITIONS, *extra]


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(
    request: Request,
    run_id: int,
    min_sources: int = Query(2, ge=1, le=10),
    region: str | None = Query(None, max_length=40),
    subject: str | None = Query(None, max_length=40),
) -> HTMLResponse:
    if run_id > 2**31 - 1:
        raise HTTPException(404, "Run not found")
    runs = query("SELECT * FROM cluster_runs ORDER BY created_at DESC, id DESC")
    run = next((r for r in runs if r["id"] == run_id), None)
    if run is None:
        raise HTTPException(404, "Run not found")
    clusters, members = load_clusters(run_id, min_sources, region, subject)

    def link(**overrides: Any) -> str:
        params = {"min_sources": min_sources, "region": region, "subject": subject, **overrides}
        return f"/runs/{run_id}?" + urlencode({k: v for k, v in params.items() if v is not None})

    edition_links = []
    for code in edition_codes(runs):
        of_edition = [r for r in runs if r["edition"] == code]
        target = next((r for r in of_edition if abs(r["threshold"] - run["threshold"]) <= THRESHOLD_TOLERANCE), None)
        target = target or next(iter(of_edition), None)
        edition_links.append({"code": code, "run": target})
    total = query("SELECT count(*) AS n FROM clusters WHERE run_id = %s", (run_id,))[0]["n"]
    ctx = {
        "run": run,
        "runs": [r for r in runs if r["edition"] == run["edition"]],
        "edition_links": edition_links,
        "clusters": clusters,
        "members": members,
        "min_sources": min_sources,
        "total": total,
        "region": region,
        "subject": subject,
        "regions": facet_counts(run_id, "region", min_sources),
        "subjects": facet_counts(run_id, "subject", min_sources),
        "link": link,
        "none_value": NONE,
    }
    return templates.TemplateResponse(request, "run.html", ctx)


@app.get("/stories", response_class=HTMLResponse)
def stories_page(
    request: Request,
    edition: str = Query("mk", max_length=20),
    view: str = Query("top", pattern="^(top|latest)$"),
    min_sources: int = Query(2, ge=1, le=10),
    region: str | None = Query(None, max_length=40),
    subject: str | None = Query(None, max_length=40),
) -> HTMLResponse:
    stories, members = load_stories(edition, view, min_sources, region, subject)

    def link(**overrides: Any) -> str:
        params = {"edition": edition, "view": view, "min_sources": min_sources, "region": region, "subject": subject}
        params.update(overrides)
        return "/stories?" + urlencode({k: v for k, v in params.items() if v is not None})

    ctx = {
        "edition": edition,
        "editions": story_editions(),
        "view": view,
        "views": VIEWS,
        "min_sources": min_sources,
        "region": region,
        "subject": subject,
        "stories": stories,
        "members": members,
        "regions": story_facets(edition, "region", min_sources),
        "subjects": story_facets(edition, "subject", min_sources),
        "link": link,
        "none_value": NONE,
    }
    return templates.TemplateResponse(request, "stories.html", ctx)


@app.get("/editions", response_class=HTMLResponse)
def editions(
    request: Request,
    view: str = Query("top", pattern="^(top|latest)$"),
    min_sources: int = Query(2, ge=1, le=10),
) -> HTMLResponse:
    panels = []
    for code in story_editions():
        stories, members = load_stories(code, view, min_sources)
        panels.append(
            {
                "code": code,
                "stories": stories,
                "members": members,
                "regions": story_facets(code, "region", min_sources),
                "subjects": story_facets(code, "subject", min_sources),
            }
        )
    ctx = {"panels": panels, "view": view, "views": VIEWS, "min_sources": min_sources, "none_value": NONE}
    return templates.TemplateResponse(request, "editions.html", ctx)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> PlainTextResponse:
    try:
        query("SELECT 1")
    except psycopg.Error:
        return PlainTextResponse("db unavailable", status_code=503)
    return PlainTextResponse("ok")
