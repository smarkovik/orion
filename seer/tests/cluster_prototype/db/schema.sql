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

-- Categories (idempotent, also applied to existing databases by `make migrate`).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_categories text[] NOT NULL DEFAULT '{}';
ALTER TABLE clusters
    ADD COLUMN IF NOT EXISTS region         text,
    ADD COLUMN IF NOT EXISTS region_votes   int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS subject        text,
    ADD COLUMN IF NOT EXISTS subject_votes  int NOT NULL DEFAULT 0;

-- Editions (idempotent). An edition is clustered on its own; sources.language holds the edition code.
ALTER TABLE cluster_runs ADD COLUMN IF NOT EXISTS edition text NOT NULL DEFAULT 'mk';

-- Images and content updates (idempotent).
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS image_url           text,
    ADD COLUMN IF NOT EXISTS source_modified_at  timestamptz,
    ADD COLUMN IF NOT EXISTS checked_at          timestamptz,
    ADD COLUMN IF NOT EXISTS content_changed_at  timestamptz,
    ADD COLUMN IF NOT EXISTS change_count        int NOT NULL DEFAULT 0;

-- Stable stories, built incrementally (one live model and threshold; cluster_runs stay for experiments).
CREATE TABLE IF NOT EXISTS stories (
    id                bigserial PRIMARY KEY,
    edition           text NOT NULL,
    model             text NOT NULL,
    threshold         real NOT NULL,
    state             text NOT NULL DEFAULT 'open',
    created_at        timestamptz NOT NULL DEFAULT now(),
    last_activity_at  timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz,
    label_article_id  bigint REFERENCES articles(id),
    size              int NOT NULL DEFAULT 0,
    source_count      int NOT NULL DEFAULT 0,
    first_published   timestamptz,
    last_published    timestamptz,
    score             real NOT NULL DEFAULT 0,
    region            text,
    region_votes      int NOT NULL DEFAULT 0,
    subject           text,
    subject_votes     int NOT NULL DEFAULT 0,
    centroid          vector(768)
);
CREATE INDEX IF NOT EXISTS stories_top_idx ON stories (edition, state, score DESC);
CREATE INDEX IF NOT EXISTS stories_latest_idx ON stories (edition, created_at DESC);

CREATE TABLE IF NOT EXISTS story_articles (
    story_id    bigint NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    article_id  bigint NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    similarity  real NOT NULL,
    joined_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (story_id, article_id)
);
