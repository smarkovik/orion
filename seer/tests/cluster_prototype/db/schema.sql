CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sources (
    id        serial PRIMARY KEY,
    name      text NOT NULL,
    domain    text NOT NULL UNIQUE,
    base_url  text NOT NULL,
    language  text NOT NULL DEFAULT 'mk'
);

CREATE TABLE IF NOT EXISTS articles (
    id            bigserial PRIMARY KEY,
    source_id     int NOT NULL REFERENCES sources(id),
    url           text NOT NULL UNIQUE,
    external_id   text,
    title         text NOT NULL,
    body          text NOT NULL DEFAULT '',
    published_at  timestamptz,
    fetched_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    content_hash  text NOT NULL
);
CREATE INDEX IF NOT EXISTS articles_published_idx ON articles (published_at DESC);

-- 768 = intfloat/multilingual-e5-base
CREATE TABLE IF NOT EXISTS embeddings (
    article_id    bigint NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    model         text NOT NULL,
    content_hash  text NOT NULL,
    vector        vector(768) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (article_id, model)
);

CREATE TABLE IF NOT EXISTS cluster_runs (
    id                  serial PRIMARY KEY,
    created_at          timestamptz NOT NULL DEFAULT now(),
    model               text NOT NULL,
    method              text NOT NULL,
    threshold           real NOT NULL,
    window_hours        int NOT NULL,
    article_count       int NOT NULL,
    cluster_count       int NOT NULL,
    multi_source_count  int NOT NULL,
    largest_cluster     int NOT NULL
);

CREATE TABLE IF NOT EXISTS clusters (
    id                bigserial PRIMARY KEY,
    run_id            int NOT NULL REFERENCES cluster_runs(id) ON DELETE CASCADE,
    label_article_id  bigint NOT NULL REFERENCES articles(id),
    size              int NOT NULL,
    source_count      int NOT NULL,
    first_published   timestamptz,
    last_published    timestamptz,
    score             real NOT NULL
);
CREATE INDEX IF NOT EXISTS clusters_run_idx ON clusters (run_id, source_count DESC, size DESC);

CREATE TABLE IF NOT EXISTS cluster_articles (
    cluster_id  bigint NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    article_id  bigint NOT NULL REFERENCES articles(id),
    similarity  real NOT NULL,
    PRIMARY KEY (cluster_id, article_id)
);
