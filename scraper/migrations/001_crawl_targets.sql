CREATE TABLE IF NOT EXISTS crawl_targets (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    type            VARCHAR(20) NOT NULL CHECK (type IN ('manufacturer', 'series', 'model')),
    parent_id       BIGINT,
    meta            JSONB DEFAULT '{}',
    last_crawled_at TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending'
                        CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    content_hash    VARCHAR(64),
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crawl_targets_status_type
    ON crawl_targets (status, type);

CREATE INDEX IF NOT EXISTS idx_crawl_targets_parent
    ON crawl_targets (parent_id);
