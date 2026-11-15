import os
import time
from typing import Any

import yaml
from pgvector.psycopg import register_vector

import cluster
from seer_common import db


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    start = time.perf_counter()
    with open(os.environ.get("CATEGORIES_FILE", "/var/task/categories.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    editions: dict[str, dict[str, int]] = {}
    with db.connect(autocommit=True) as conn:
        register_vector(conn)
        embedded, embed_s = cluster.embed_pending(conn)
        wanted = (event or {}).get("editions")
        if not wanted:
            wanted = [r[0] for r in conn.execute("SELECT DISTINCT language FROM sources ORDER BY 1").fetchall()]
        for edition in wanted:
            editions[edition] = cluster.run_stories(conn, edition, cluster.CategoryMap(cfg, edition))
    return {
        "embedded": embedded,
        "embed_s": round(embed_s, 2),
        "editions": editions,
        "duration_s": round(time.perf_counter() - start, 2),
    }
