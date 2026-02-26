-- Add tractor_type ('farm' | 'lawn') to series and tractor_models.
-- Manufacturers themselves are NOT typed: a brand can appear in both categories.

ALTER TABLE series
    ADD COLUMN IF NOT EXISTS tractor_type VARCHAR(10)
        CHECK (tractor_type IN ('farm', 'lawn'));

ALTER TABLE tractor_models
    ADD COLUMN IF NOT EXISTS tractor_type VARCHAR(10)
        CHECK (tractor_type IN ('farm', 'lawn'));

CREATE INDEX IF NOT EXISTS idx_series_tractor_type
    ON series (tractor_type);

CREATE INDEX IF NOT EXISTS idx_models_tractor_type
    ON tractor_models (tractor_type);
