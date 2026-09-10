-- Promotion Impact & Causal Analysis Data Warehouse — Star Schema
-- Grain of Fact_Daily_Sales: one row per (store, day)

DROP TABLE IF EXISTS Fact_Daily_Sales;
DROP TABLE IF EXISTS Dim_Date;
DROP TABLE IF EXISTS Dim_Store;

CREATE TABLE Dim_Date (
    Date_Key            INTEGER PRIMARY KEY,   -- YYYYMMDD
    Full_Date           TEXT NOT NULL,
    Year                INTEGER NOT NULL,
    Month               INTEGER NOT NULL,
    Month_Name          TEXT NOT NULL,
    Year_Month           TEXT NOT NULL,        -- 'YYYY-MM', used as the time-fixed-effect key
    Day                 INTEGER NOT NULL,
    Day_Of_Week          INTEGER NOT NULL,      -- 1=Monday ... 7=Sunday (matches raw DayOfWeek)
    Day_Name             TEXT NOT NULL,
    Is_Weekend            INTEGER NOT NULL,      -- 0/1
    State_Holiday_Type    TEXT NOT NULL,         -- 'None' / 'Public' / 'Easter' / 'Christmas'
    Is_State_Holiday      INTEGER NOT NULL,      -- 0/1
    Is_School_Holiday_Any INTEGER NOT NULL       -- 1 if ANY store reports a school holiday that date (state-level signal)
);

CREATE TABLE Dim_Store (
    Store_Key                      INTEGER PRIMARY KEY,   -- same as raw Store id
    Store_Type                     TEXT NOT NULL,          -- a/b/c/d
    Assortment                     TEXT NOT NULL,          -- a=basic, b=extra, c=extended
    Competition_Distance_M         REAL,                    -- meters to nearest competitor
    Is_Competition_Distance_Imputed INTEGER NOT NULL DEFAULT 0,
    Competition_Open_Since_Month   INTEGER,
    Competition_Open_Since_Year    INTEGER,
    Has_Promo2                     INTEGER NOT NULL,       -- 0/1, enrolled in the continuing "Promo2" loyalty program
    Promo2_Since_Week              INTEGER,
    Promo2_Since_Year              INTEGER,
    Promo2_Interval                TEXT
);

CREATE TABLE Fact_Daily_Sales (
    Fact_Key            INTEGER PRIMARY KEY AUTOINCREMENT,
    Date_Key             INTEGER NOT NULL REFERENCES Dim_Date(Date_Key),
    Store_Key             INTEGER NOT NULL REFERENCES Dim_Store(Store_Key),
    Sales                REAL NOT NULL,
    Customers            INTEGER NOT NULL,
    Promo                INTEGER NOT NULL,       -- 0/1, single-day promo flag (the treatment)
    School_Holiday        INTEGER NOT NULL,       -- 0/1, this store's local school holiday flag
    Is_Sales_Anomaly      INTEGER NOT NULL DEFAULT 0  -- store marked Open=1 but Sales=0 (register/reporting glitch)
);

CREATE INDEX idx_fact_date ON Fact_Daily_Sales(Date_Key);
CREATE INDEX idx_fact_store ON Fact_Daily_Sales(Store_Key);
CREATE INDEX idx_fact_promo ON Fact_Daily_Sales(Promo);
