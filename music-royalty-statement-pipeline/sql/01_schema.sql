-- Music Royalty Statement Pipeline — star-schema warehouse (SQLite)
DROP TABLE IF EXISTS fact_royalty_line;
DROP TABLE IF EXISTS quarantine_line;
DROP TABLE IF EXISTS statement_register;
DROP TABLE IF EXISTS validation_exception;
DROP TABLE IF EXISTS dim_track;
DROP TABLE IF EXISTS dim_territory;
DROP TABLE IF EXISTS dim_distributor;
DROP TABLE IF EXISTS dim_period;

CREATE TABLE dim_track (
    track_id     TEXT PRIMARY KEY,      -- Spotify track ID from the master catalog
    song_id      TEXT,                  -- song-level ID shared by every release of the same recording
    title        TEXT,
    artist       TEXT,
    distributor  TEXT                    -- distributor that administers this catalog
);

CREATE TABLE dim_territory (
    territory_name TEXT,
    iso2           TEXT PRIMARY KEY,
    iso3           TEXT,
    tier           INTEGER,             -- illustrative market pay-rate tier (1 = highest)
    rate_usd       REAL                 -- illustrative per-stream rate for that tier
);

CREATE TABLE dim_distributor (
    distributor    TEXT PRIMARY KEY,
    file_format    TEXT,
    currency       TEXT,
    sends_track_id INTEGER
);

CREATE TABLE dim_period (
    period  TEXT PRIMARY KEY,           -- YYYY-MM
    year    INTEGER,
    month   INTEGER,
    quarter INTEGER,
    chart_weeks INTEGER                 -- weekly chart snapshots in the month (4 or 5; Oct 2019 = 3)
);

-- One row per validated statement line (grain: statement x track x territory x sale month)
CREATE TABLE fact_royalty_line (
    statement_file   TEXT,
    distributor      TEXT REFERENCES dim_distributor(distributor),
    statement_period TEXT REFERENCES dim_period(period),
    sale_period      TEXT REFERENCES dim_period(period),
    track_id         TEXT REFERENCES dim_track(track_id),   -- NULL when source sent no ID and the song has several
    song_id          TEXT,
    territory_iso2   TEXT REFERENCES dim_territory(iso2),
    streams          INTEGER,
    currency         TEXT,
    gross_local      REAL,
    net_local        REAL,
    gross_usd        REAL,
    net_usd          REAL,
    is_adjustment    INTEGER             -- 1 = reversal / chargeback line
);
CREATE INDEX ix_fact_song   ON fact_royalty_line(song_id);
CREATE INDEX ix_fact_period ON fact_royalty_line(sale_period);
CREATE INDEX ix_fact_dist   ON fact_royalty_line(distributor, statement_period);

-- Lines held back from the fact table until someone reviews them
CREATE TABLE quarantine_line (
    statement_file    TEXT,
    distributor       TEXT,
    statement_period  TEXT,
    sale_period       TEXT,
    line_no           INTEGER,
    track_id          TEXT,
    song_id           TEXT,
    title_raw         TEXT,
    artist_raw        TEXT,
    territory_iso2    TEXT,
    streams           INTEGER,
    currency          TEXT,
    gross_local       REAL,
    net_local         REAL,
    quarantine_reason TEXT
);

-- One row per statement file received: what came in, what loaded, and its status
CREATE TABLE statement_register (
    statement_file     TEXT PRIMARY KEY,
    distributor        TEXT,
    statement_period   TEXT,
    currency           TEXT,
    rows_in            INTEGER,
    footer_total_local REAL,
    read_seconds       REAL,
    rows_loaded        INTEGER,
    rows_quarantined   INTEGER,
    status             TEXT             -- AUTO-PASS / REVIEW / REJECTED
);

CREATE TABLE validation_exception (
    check_name     TEXT,
    severity       TEXT,                -- HIGH / MEDIUM / LOW
    statement_file TEXT,
    rows_affected  INTEGER,
    detail         TEXT
);
