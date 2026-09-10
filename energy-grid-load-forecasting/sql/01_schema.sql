-- Energy Grid Load Forecasting Data Warehouse — Star Schema
-- Grain of Fact_Hourly_Demand: one row per (zone, hour)

DROP TABLE IF EXISTS Fact_Hourly_Demand;
DROP TABLE IF EXISTS Dim_Date;
DROP TABLE IF EXISTS Dim_Zone;

CREATE TABLE Dim_Date (
    Date_Key        INTEGER PRIMARY KEY,   -- YYYYMMDD
    Full_Date       TEXT NOT NULL,
    Year            INTEGER NOT NULL,
    Quarter         INTEGER NOT NULL,
    Month           INTEGER NOT NULL,
    Month_Name      TEXT NOT NULL,
    Day             INTEGER NOT NULL,
    Day_Of_Week     INTEGER NOT NULL,      -- 0=Monday ... 6=Sunday
    Day_Name        TEXT NOT NULL,
    Is_Weekend      INTEGER NOT NULL,      -- 0/1
    Season          TEXT NOT NULL          -- Winter/Spring/Summer/Fall
);

CREATE TABLE Dim_Zone (
    Zone_Key        INTEGER PRIMARY KEY AUTOINCREMENT,
    Zone_Code       TEXT NOT NULL UNIQUE,  -- e.g. 'AEP'
    Zone_Name       TEXT NOT NULL,         -- e.g. 'American Electric Power'
    States_Served   TEXT NOT NULL,
    Parent_ISO      TEXT NOT NULL          -- 'PJM Interconnection'
);

CREATE TABLE Fact_Hourly_Demand (
    Fact_Key            INTEGER PRIMARY KEY AUTOINCREMENT,
    Date_Key            INTEGER NOT NULL REFERENCES Dim_Date(Date_Key),
    Zone_Key            INTEGER NOT NULL REFERENCES Dim_Zone(Zone_Key),
    Hour_Of_Day         INTEGER NOT NULL,      -- 0-23
    Demand_MW           REAL NOT NULL,
    Is_DST_Duplicate    INTEGER NOT NULL DEFAULT 0,  -- ambiguous 2 AM fall-back reading
    Is_Interpolated     INTEGER NOT NULL DEFAULT 0   -- filled for a DST spring-forward gap
);

CREATE INDEX idx_fact_date ON Fact_Hourly_Demand(Date_Key);
CREATE INDEX idx_fact_zone ON Fact_Hourly_Demand(Zone_Key);
