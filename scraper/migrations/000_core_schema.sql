-- Core schema: manufacturers, series, tractor_models, model_specifications
-- tractor_type ('farm' | 'lawn') is included from the start on series and models.

CREATE TABLE IF NOT EXISTS manufacturers (
    id          BIGSERIAL PRIMARY KEY,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    name        VARCHAR(255) NOT NULL,
    country     VARCHAR(100),
    description TEXT,
    name_search TSVECTOR,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manufacturers_name_search
    ON manufacturers USING GIN (name_search);

CREATE TABLE IF NOT EXISTS series (
    id                   BIGSERIAL PRIMARY KEY,
    manufacturer_id      BIGINT NOT NULL REFERENCES manufacturers (id) ON DELETE CASCADE,
    slug                 VARCHAR(120) NOT NULL,
    name                 VARCHAR(255) NOT NULL,
    tractor_type         VARCHAR(10) CHECK (tractor_type IN ('farm', 'lawn')),
    production_start_year INT,
    production_end_year   INT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (manufacturer_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_series_manufacturer
    ON series (manufacturer_id);

CREATE INDEX IF NOT EXISTS idx_series_tractor_type
    ON series (tractor_type);

CREATE TABLE IF NOT EXISTS tractor_models (
    id                   BIGSERIAL PRIMARY KEY,
    manufacturer_id      BIGINT NOT NULL REFERENCES manufacturers (id) ON DELETE CASCADE,
    series_id            BIGINT REFERENCES series (id) ON DELETE SET NULL,
    slug                 VARCHAR(255) NOT NULL UNIQUE,
    name                 VARCHAR(255) NOT NULL,
    tractor_type         VARCHAR(10) CHECK (tractor_type IN ('farm', 'lawn')),
    production_start_year INT,
    production_end_year   INT,
    horsepower_hp        NUMERIC(8, 2),
    description          TEXT,
    name_search          TSVECTOR,
    content_hash         VARCHAR(64),
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_manufacturer
    ON tractor_models (manufacturer_id);

CREATE INDEX IF NOT EXISTS idx_models_series
    ON tractor_models (series_id);

CREATE INDEX IF NOT EXISTS idx_models_tractor_type
    ON tractor_models (tractor_type);

CREATE INDEX IF NOT EXISTS idx_models_name_search
    ON tractor_models USING GIN (name_search);

CREATE TABLE IF NOT EXISTS model_specifications (
    id            BIGSERIAL PRIMARY KEY,
    model_id      BIGINT NOT NULL REFERENCES tractor_models (id) ON DELETE CASCADE,
    spec_group    VARCHAR(120) NOT NULL,
    spec_key      VARCHAR(255) NOT NULL,
    spec_value    TEXT,
    unit          VARCHAR(50),
    display_order INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_specs_model
    ON model_specifications (model_id);
