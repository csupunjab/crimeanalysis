-- CSU Crime Analysis Portal: local dev schema
-- Covers the 3 tables this app queries (districts, divisions, crime_daily).
-- These live in the shared "csu_control_room" Postgres database in production;
-- locally you can create a dedicated database with just these tables.
--
-- Usage: psql -U postgres -d csu_control_room -f schema.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE divisions (
    id SERIAL PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_ur TEXT
);

CREATE TABLE districts (
    id SERIAL PRIMARY KEY,
    division_id INTEGER REFERENCES divisions(id),
    name_en TEXT NOT NULL,
    name_ur TEXT,
    code TEXT UNIQUE,
    centroid_lat NUMERIC(10,8),
    centroid_lng NUMERIC(11,8),
    region_id INTEGER,
    exclude_from_analysis BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE crime_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL,
    district_id INTEGER NOT NULL REFERENCES districts(id),
    murder INTEGER NOT NULL DEFAULT 0,
    dacoity INTEGER NOT NULL DEFAULT 0,
    robbery INTEGER NOT NULL DEFAULT 0,
    dacoity_robbery_murder INTEGER NOT NULL DEFAULT 0,
    dacoity_robbery_injury INTEGER NOT NULL DEFAULT 0,
    dacoity_robbery_rape INTEGER NOT NULL DEFAULT 0,
    snatching_jhappata INTEGER NOT NULL DEFAULT 0,
    child_abuse INTEGER NOT NULL DEFAULT 0,
    rape INTEGER NOT NULL DEFAULT 0,
    gang_rape INTEGER NOT NULL DEFAULT 0,
    sodomy INTEGER NOT NULL DEFAULT 0,
    road_accident_casualties INTEGER NOT NULL DEFAULT 0,
    acid_attack INTEGER NOT NULL DEFAULT 0,
    religious_issues INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (report_date, district_id)
);

CREATE INDEX idx_crime_daily_date ON crime_daily (report_date DESC);
CREATE INDEX idx_crime_daily_district ON crime_daily (district_id);
