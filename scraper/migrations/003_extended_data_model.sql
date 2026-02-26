-- Extended data model: categories, sub-page tables, extra model columns
-- Adds support for engine, transmission, dimensions/tires, tests, and photos
-- sub-page crawling.

-- ---------------------------------------------------------------------------
-- categories
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS categories (
    id          BIGSERIAL PRIMARY KEY,
    slug        VARCHAR(60)  NOT NULL UNIQUE,
    name        VARCHAR(120) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO categories (slug, name) VALUES
    ('farm',        'Farm / Row-Crop'),
    ('lawn-garden', 'Lawn & Garden'),
    ('utility',     'Utility'),
    ('orchard',     'Orchard'),
    ('industrial',  'Industrial')
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Extend manufacturers
-- ---------------------------------------------------------------------------

ALTER TABLE manufacturers
    ADD COLUMN IF NOT EXISTS founded_year SMALLINT,
    ADD COLUMN IF NOT EXISTS logo_path    VARCHAR(255);

-- ---------------------------------------------------------------------------
-- Extend tractor_models
-- ---------------------------------------------------------------------------

ALTER TABLE tractor_models
    ADD COLUMN IF NOT EXISTS category_id      BIGINT REFERENCES categories (id),
    ADD COLUMN IF NOT EXISTS drive_type       VARCHAR(80),
    ADD COLUMN IF NOT EXISTS steering_type    VARCHAR(120),
    ADD COLUMN IF NOT EXISTS brake_type       VARCHAR(120),
    ADD COLUMN IF NOT EXISTS cab_description  TEXT,
    ADD COLUMN IF NOT EXISTS fuel_tank_l      NUMERIC(8, 2),
    ADD COLUMN IF NOT EXISTS def_tank_l       NUMERIC(8, 2),
    ADD COLUMN IF NOT EXISTS seo_title        VARCHAR(255),
    ADD COLUMN IF NOT EXISTS seo_description  VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_models_category
    ON tractor_models (category_id);

-- ---------------------------------------------------------------------------
-- model_engines
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_engines (
    id                      BIGSERIAL PRIMARY KEY,
    model_id                BIGINT NOT NULL REFERENCES tractor_models (id) ON DELETE CASCADE,
    -- Identity
    engine_manufacturer     VARCHAR(120),
    fuel_type               VARCHAR(120),
    cylinders               SMALLINT,
    cooling                 VARCHAR(60),
    -- Displacement
    displacement_ci         NUMERIC(8, 2),
    displacement_l          NUMERIC(6, 3),
    -- Bore / stroke
    bore_in                 NUMERIC(6, 3),
    bore_mm                 NUMERIC(6, 1),
    stroke_in               NUMERIC(6, 3),
    stroke_mm               NUMERIC(6, 1),
    -- Emissions
    emissions_tier          VARCHAR(60),
    emission_control        TEXT,
    -- Power
    rated_power_hp          NUMERIC(8, 2),
    rated_power_kw          NUMERIC(8, 2),
    rated_rpm               INT,
    -- Torque
    torque_lbft             NUMERIC(8, 2),
    torque_nm               NUMERIC(8, 2),
    torque_rpm              INT,
    -- Starter
    starter_type            VARCHAR(60),
    starter_volts           NUMERIC(5, 1),
    starter_hp              NUMERIC(6, 2),
    -- Maintenance
    oil_change_hours        INT,
    -- Raw source for anything not yet modelled
    raw_data                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_id)
);

CREATE INDEX IF NOT EXISTS idx_engines_model
    ON model_engines (model_id);

-- ---------------------------------------------------------------------------
-- model_tire_options
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_tire_options (
    id              BIGSERIAL PRIMARY KEY,
    model_id        BIGINT NOT NULL REFERENCES tractor_models (id) ON DELETE CASCADE,
    option_label    VARCHAR(120),           -- e.g. "Standard", "Optional"
    front_tire      VARCHAR(80),
    rear_tire       VARCHAR(80),
    -- Full dimensions stored on first/primary row (standard tires)
    wheelbase_in    NUMERIC(7, 2),
    wheelbase_cm    NUMERIC(7, 1),
    length_in       NUMERIC(7, 2),
    length_cm       NUMERIC(7, 1),
    width_in        NUMERIC(7, 2),
    width_cm        NUMERIC(7, 1),
    height_in       NUMERIC(7, 2),
    height_cm       NUMERIC(7, 1),
    weight_lbs      NUMERIC(10, 1),
    weight_kg       NUMERIC(10, 1),
    ground_clearance_in  NUMERIC(6, 2),
    ground_clearance_cm  NUMERIC(6, 1),
    front_tread_in  NUMERIC(6, 2),
    front_tread_cm  NUMERIC(6, 1),
    rear_tread_in   NUMERIC(6, 2),
    rear_tread_cm   NUMERIC(6, 1),
    display_order   SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tire_options_model
    ON model_tire_options (model_id);

-- ---------------------------------------------------------------------------
-- model_tests
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_tests (
    id                   BIGSERIAL PRIMARY KEY,
    model_id             BIGINT NOT NULL REFERENCES tractor_models (id) ON DELETE CASCADE,
    test_name            VARCHAR(255),
    test_date_start      DATE,
    test_date_end        DATE,
    test_url             TEXT,
    -- PTO power
    pto_max_hp           NUMERIC(8, 2),
    pto_max_kw           NUMERIC(8, 2),
    pto_max_fuel_gph     NUMERIC(8, 3),
    pto_rated_eng_hp     NUMERIC(8, 2),
    pto_rated_eng_kw     NUMERIC(8, 2),
    pto_rated_pto_hp     NUMERIC(8, 2),
    pto_rated_pto_kw     NUMERIC(8, 2),
    -- Drawbar power
    drawbar_max_hp       NUMERIC(8, 2),
    drawbar_max_kw       NUMERIC(8, 2),
    drawbar_max_fuel_gph NUMERIC(8, 3),
    drawbar_max_pull_lbs NUMERIC(10, 1),
    drawbar_max_pull_kg  NUMERIC(10, 1),
    -- Raw source
    raw_data             JSONB DEFAULT '{}',
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tests_model
    ON model_tests (model_id);

-- ---------------------------------------------------------------------------
-- model_photos
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_photos (
    id              BIGSERIAL PRIMARY KEY,
    model_id        BIGINT NOT NULL REFERENCES tractor_models (id) ON DELETE CASCADE,
    image_url       TEXT NOT NULL,
    attribution     TEXT,
    display_order   SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_photos_model
    ON model_photos (model_id);

-- ---------------------------------------------------------------------------
-- model_specifications: add missing indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_specs_group
    ON model_specifications (model_id, spec_group);

CREATE INDEX IF NOT EXISTS idx_specs_key
    ON model_specifications (spec_key);

-- ---------------------------------------------------------------------------
-- Extend crawl_targets type CHECK to include sub-page types
-- ---------------------------------------------------------------------------

-- PostgreSQL doesn't let you ALTER a CHECK constraint directly; drop and re-add.
ALTER TABLE crawl_targets
    DROP CONSTRAINT IF EXISTS crawl_targets_type_check;

ALTER TABLE crawl_targets
    ADD CONSTRAINT crawl_targets_type_check
    CHECK (type IN (
        'manufacturer',
        'series',
        'model',
        'model_engine',
        'model_transmission',
        'model_dimensions',
        'model_tests',
        'model_photos'
    ));
