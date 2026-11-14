import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://seer:seer@127.0.0.1:5433/seer")
TZ = ZoneInfo("Europe/Skopje")

app = FastAPI(title="Cluster viewer", docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def local_dt(value: datetime | None) -> str:
    return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if value else "?"


templates.env.filters["local_dt"] = local_dt


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5) as conn:
        return conn.execute(sql, params).fetchall()  # type: ignore[return-value]


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    runs = query("SELECT * FROM cluster_runs ORDER BY created_at DESC, id DESC")
    return templates.TemplateResponse(request, "index.html", {"runs": runs})


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int, min_sources: int = Query(2, ge=1, le=10)) -> HTMLResponse:
    if run_id > 2**31 - 1:
        raise HTTPException(404, "Run not found")
    runs = query("SELECT * FROM cluster_runs ORDER BY created_at DESC, id DESC")
    run = next((r for r in runs if r["id"] == run_id), None)
    if run is None:
        raise HTTPException(404, "Run not found")
    clusters = query(
        """
        SELECT c.id, c.size, c.source_count, c.first_published, c.last_published, c.score,
               a.title AS label_title, a.url AS label_url
        FROM clusters c JOIN articles a ON a.id = c.label_article_id
        WHERE c.run_id = %s AND c.source_count >= %s
        ORDER BY c.source_count DESC, c.size DESC, c.score DESC, c.id
        """,
        (run_id, min_sources),
    )
    members: dict[int, list[dict[str, Any]]] = {c["id"]: [] for c in clusters}
    if clusters:
        rows = query(
            """
            SELECT ca.cluster_id, ca.similarity, a.title, a.url, a.published_at, s.name AS source_name
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
    total = query("SELECT count(*) AS n FROM clusters WHERE run_id = %s", (run_id,))[0]["n"]
    ctx = {"run": run, "runs": runs, "clusters": clusters, "members": members, "min_sources": min_sources, "total": total}
    return templates.TemplateResponse(request, "run.html", ctx)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> PlainTextResponse:
    try:
        query("SELECT 1")
    except psycopg.Error:
        return PlainTextResponse("db unavailable", status_code=503)
    return PlainTextResponse("ok")
