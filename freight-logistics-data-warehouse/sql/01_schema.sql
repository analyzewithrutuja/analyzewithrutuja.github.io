-- ============================================================
-- Freight Logistics Data Warehouse — Star Schema DDL
-- Grain of Fact_Trips: one row per truck trip (BookingID)
-- ============================================================

DROP TABLE IF EXISTS Fact_Trips;
DROP TABLE IF EXISTS Dim_Date;
DROP TABLE IF EXISTS Dim_Supplier;
DROP TABLE IF EXISTS Dim_Customer;
DROP TABLE IF EXISTS Dim_Vehicle;
DROP TABLE IF EXISTS Dim_Location;
DROP TABLE IF EXISTS Dim_GPS_Provider;

-- ---------------------------------------------------------
-- Dimension: Date (standard calendar dimension)
-- ---------------------------------------------------------
CREATE TABLE Dim_Date (
    Date_Key        INTEGER PRIMARY KEY,   -- YYYYMMDD
    Full_Date       TEXT NOT NULL,
    Year            INTEGER NOT NULL,
    Quarter         INTEGER NOT NULL,
    Month           INTEGER NOT NULL,
    Month_Name      TEXT NOT NULL,
    Week_Of_Year    INTEGER NOT NULL,
    Day_Of_Week     TEXT NOT NULL,
    Is_Weekend      INTEGER NOT NULL       -- 1 = Sat/Sun, 0 = weekday
);

-- ---------------------------------------------------------
-- Dimension: Supplier (the trucking/transport carrier)
-- ---------------------------------------------------------
CREATE TABLE Dim_Supplier (
    Supplier_Key        INTEGER PRIMARY KEY AUTOINCREMENT,
    Supplier_ID         TEXT UNIQUE,
    Supplier_Name        TEXT NOT NULL
);

-- ---------------------------------------------------------
-- Dimension: Customer (the shipper / OEM placing the order)
-- ---------------------------------------------------------
CREATE TABLE Dim_Customer (
    Customer_Key        INTEGER PRIMARY KEY AUTOINCREMENT,
    Customer_ID          TEXT UNIQUE,
    Customer_Name        TEXT NOT NULL
);

-- ---------------------------------------------------------
-- Dimension: Vehicle (cleaned/standardized vehicle type)
-- ---------------------------------------------------------
CREATE TABLE Dim_Vehicle (
    Vehicle_Key           INTEGER PRIMARY KEY AUTOINCREMENT,
    Vehicle_No             TEXT UNIQUE,
    Vehicle_Type_Raw       TEXT,
    Vehicle_Type_Clean     TEXT,
    Vehicle_Category       TEXT              -- e.g. Trailer / HCV / MCV / LCV / Container / Pickup / Unknown
);

-- ---------------------------------------------------------
-- Dimension: Location (role-playing — used for both Origin
-- and Destination via separate foreign keys on the fact table).
-- Built at City/State grain: the source system's facility-level
-- location codes did not map 1:1 to a single facility name/city/
-- state (dozens of codes were reused across differently-named
-- facilities), so City/State is the cleanest reliable grain and
-- also the right grain for lane-level BI reporting.
-- ---------------------------------------------------------
CREATE TABLE Dim_Location (
    Location_Key          INTEGER PRIMARY KEY AUTOINCREMENT,
    City                    TEXT,
    State                   TEXT,
    UNIQUE(City, State)
);

-- ---------------------------------------------------------
-- Dimension: GPS Provider (tracking vendor used for the trip)
-- ---------------------------------------------------------
CREATE TABLE Dim_GPS_Provider (
    GPS_Provider_Key       INTEGER PRIMARY KEY AUTOINCREMENT,
    Provider_Name           TEXT UNIQUE
);

-- ---------------------------------------------------------
-- Fact: Trips
-- ---------------------------------------------------------
CREATE TABLE Fact_Trips (
    Trip_Key                    INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_ID                   TEXT UNIQUE NOT NULL,
    Date_Key                     INTEGER NOT NULL REFERENCES Dim_Date(Date_Key),
    Supplier_Key                 INTEGER REFERENCES Dim_Supplier(Supplier_Key),
    Customer_Key                 INTEGER REFERENCES Dim_Customer(Customer_Key),
    Vehicle_Key                  INTEGER REFERENCES Dim_Vehicle(Vehicle_Key),
    Origin_Location_Key          INTEGER REFERENCES Dim_Location(Location_Key),
    Destination_Location_Key     INTEGER REFERENCES Dim_Location(Location_Key),
    GPS_Provider_Key             INTEGER REFERENCES Dim_GPS_Provider(GPS_Provider_Key),
    Market_Type                  TEXT,          -- Regular / Market
    Trip_Start_Date              TEXT,
    Trip_End_Date                TEXT,
    Planned_ETA                  TEXT,
    Actual_ETA                   TEXT,
    Distance_KM                  REAL,
    Min_KM_Per_Day               REAL,
    Planned_Transit_Hours        REAL,
    Actual_Transit_Hours         REAL,
    Delay_Hours                  REAL,          -- Actual_ETA - Planned_ETA, in hours (+ = late, - = early)
    On_Time_Flag                 INTEGER,       -- 1 = on time / early, 0 = late, NULL = indeterminate
    Raw_Status_Flag               TEXT,         -- original 'G'/'R' code, kept for audit/reconciliation
    Status_Match                  INTEGER,      -- 1 = derived flag agrees with raw G/R code, 0 = mismatch, NULL = no raw code
    Has_Missing_Distance          INTEGER,      -- data-quality flag
    Has_Missing_Vehicle_Type      INTEGER       -- data-quality flag
);

CREATE INDEX idx_fact_date ON Fact_Trips(Date_Key);
CREATE INDEX idx_fact_supplier ON Fact_Trips(Supplier_Key);
CREATE INDEX idx_fact_vehicle ON Fact_Trips(Vehicle_Key);
CREATE INDEX idx_fact_origin ON Fact_Trips(Origin_Location_Key);
CREATE INDEX idx_fact_dest ON Fact_Trips(Destination_Location_Key);
