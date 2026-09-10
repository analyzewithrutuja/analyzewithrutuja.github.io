"""
Freight Logistics Data Warehouse — ETL Pipeline
=================================================
Extracts raw truck-trip data (GPS-tracked freight trips for an Indian
auto-parts logistics network), cleans and standardizes it, and loads it
into a star-schema SQLite data warehouse for BI reporting (Tableau).

Source data: "Delivery Truck Trip Data" (originally published on Kaggle
by ramakrishnanthiyagu; mirrored on GitHub for this project). One row
per truck trip/booking, with planned vs. actual arrival timestamps,
vehicle, carrier ("supplier"), customer, origin/destination and GPS
tracking provider.

Usage:
    python3 etl_pipeline.py
"""
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "delivery_truck_trips_raw.xlsx"
CLEAN_CSV_PATH = ROOT / "data" / "processed" / "trips_cleaned.csv"
SCHEMA_PATH = ROOT / "sql" / "01_schema.sql"
DB_PATH = ROOT / "output" / "trucking_dw.db"
TABLEAU_EXTRACT_PATH = ROOT / "output" / "tableau_extract_trips.csv"
ETL_LOG_PATH = ROOT / "output" / "etl_run_log.txt"

# SQLite needs real POSIX file locking for its rollback-journal/WAL files,
# which the mounted project folder (a network/FUSE mount) does not
# reliably support. Build the database on local disk, then copy the
# finished file out to the project's output/ folder.
BUILD_DB_PATH = Path(tempfile.gettempdir()) / "trucking_dw_build.db"


# ----------------------------------------------------------------------
# EXTRACT
# ----------------------------------------------------------------------
def extract() -> pd.DataFrame:
    return pd.read_excel(RAW_PATH)


# ----------------------------------------------------------------------
# TRANSFORM helpers
# ----------------------------------------------------------------------
def clean_vehicle_type(raw):
    """Standardize inconsistent vehicleType strings (e.g. '24 / 26 FT'
    vs '24 | 26 FT') and bucket into a coarse vehicle category."""
    if pd.isna(raw):
        return None, "Unknown"
    s = str(raw).strip()
    s_norm = re.sub(r"\s*[/|]\s*", "/", s)
    s_norm = re.sub(r"\s+", " ", s_norm).strip()
    upper = s_norm.upper()
    if "TRAILER" in upper:
        category = "Trailer"
    elif "CONTAINER" in upper:
        category = "Container"
    elif "HCV" in upper:
        category = "HCV"
    elif "MCV" in upper:
        category = "MCV"
    elif "LCV" in upper or "PICKUP" in upper:
        category = "LCV"
    else:
        category = "Other"
    return s_norm, category


def parse_location(raw):
    """Split 'Facility Name,City,State' into components. Handles rows
    with a missing city segment (double comma)."""
    if pd.isna(raw):
        return None, None
    parts = [p.strip() for p in str(raw).split(",") if p.strip() != ""]
    if len(parts) >= 3:
        return parts[-2], parts[-1]
    if len(parts) == 2:
        return None, parts[-1]
    return None, None


# ----------------------------------------------------------------------
# TRANSFORM
# ----------------------------------------------------------------------
def transform(df: pd.DataFrame):
    log = {}
    df = df.copy()
    log["rows_extracted"] = len(df)

    # --- de-duplicate on BookingID (grain of the fact table) ---
    before = len(df)
    df = df.drop_duplicates(subset="BookingID", keep="first")
    log["duplicate_bookings_removed"] = before - len(df)

    # --- parse all datetime columns. A handful of rows have blank/
    # time-only cells that Excel serializes as its epoch (1899-12-30);
    # treat those as missing rather than as real 1899 dates. ---
    excel_epoch_artifacts = 0
    for col in ["trip_start_date", "trip_end_date", "Planned_ETA", "actual_eta", "BookingID_Date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        bad = df[col].dt.year < 2000
        excel_epoch_artifacts += int(bad.sum())
        df.loc[bad, col] = pd.NaT
    log["excel_epoch_date_artifacts_nulled"] = excel_epoch_artifacts

    # --- standardize customer / supplier names: the source data has
    # the same ID mapped to inconsistently-cased name text (e.g.
    # "Ashok leyland limited" vs "Ashok Leyland Limited" both under
    # customerID ALLEXCHE45), which would otherwise break a 1:1
    # ID -> name dimension. Standardize to title case. ---
    before_cust_names = df["customerID"].astype(str) + "||" + df["customerNameCode"].astype(str)
    df["customerNameCode"] = df["customerNameCode"].astype(str).str.strip().str.title()
    df["supplierNameCode"] = df["supplierNameCode"].astype(str).str.strip().str.title()
    log["customer_ids_with_inconsistent_casing_fixed"] = int(
        df.groupby("customerID")["customerNameCode"].nunique().gt(1).sum() == 0
    ) and int((df.groupby("customerID")["customerNameCode"].nunique() > 1).sum())

    # --- standardize vehicle type. A given vehicle_no is sometimes
    # logged with slightly different raw strings across trips, so we
    # resolve one canonical raw string per vehicle (the most frequent
    # value logged for it) before deriving the clean/category fields,
    # so Dim_Vehicle can hold exactly one row per physical vehicle. ---
    def _mode_or_none(s: pd.Series):
        s = s.dropna()
        return s.mode().iloc[0] if not s.empty else None

    canonical_raw = df.groupby("vehicle_no")["vehicleType"].agg(_mode_or_none)
    vehicles_with_variation = int((df.groupby("vehicle_no")["vehicleType"].nunique(dropna=True) > 1).sum())
    log["vehicles_with_inconsistent_type_logging"] = vehicles_with_variation

    df["vehicleType_canonical"] = df["vehicle_no"].map(canonical_raw)
    vt = df["vehicleType_canonical"].apply(clean_vehicle_type)
    df["Vehicle_Type_Clean"] = vt.apply(lambda x: x[0])
    df["Vehicle_Category"] = vt.apply(lambda x: x[1])

    # --- parse origin / destination into City/State. The source's
    # facility-level location codes did not reliably map 1:1 to a
    # single facility name (52 origin codes / 136 destination codes
    # were reused across differently-named facilities), so we
    # dimension location at the City/State grain instead — the
    # cleanest reliable grain, and the right one for lane reporting. ---
    o = df["Origin_Location"].apply(parse_location)
    df["Origin_City"], df["Origin_State"] = zip(*o)
    d = df["Destination_Location"].apply(parse_location)
    df["Dest_City"], df["Dest_State"] = zip(*d)

    # --- standardize GPS provider (953 rows have no provider logged) ---
    df["GPS_Provider_Clean"] = (
        df["GpsProvider"].fillna("Manual / Unknown").astype(str).str.strip().str.upper()
    )

    # --- derive on-time performance from planned vs. actual ETA ---
    df["Delay_Hours"] = (df["actual_eta"] - df["Planned_ETA"]).dt.total_seconds() / 3600
    derived_flag = np.where(
        df["Delay_Hours"].isna(), np.nan, np.where(df["Delay_Hours"] <= 0, 1, 0)
    )

    # --- reconcile against the raw ontime('G') / delay('R') columns:
    # these two source columns are mutually exclusive (only one is
    # ever populated per row), so we combine them into one flag and
    # cross-check it against the ETA-derived flag as a QA step. ---
    raw_flag = np.where(df["ontime"].notna(), 1, np.where(df["delay"].notna(), 0, np.nan))
    df["Raw_Status_Flag"] = np.where(
        df["ontime"].notna(), "G", np.where(df["delay"].notna(), "R", None)
    )

    both_present = (~pd.isna(derived_flag)) & (~pd.isna(raw_flag))
    status_match = np.where(both_present, (derived_flag == raw_flag).astype(float), np.nan)
    log["eta_derived_and_raw_flag_agree"] = int(np.nansum(status_match == 1))
    log["eta_derived_and_raw_flag_disagree"] = int(np.nansum(status_match == 0))
    df["Status_Match"] = status_match

    # fall back to the raw G/R code only when ETA timestamps are missing
    on_time_flag = np.where(pd.isna(derived_flag), raw_flag, derived_flag)
    df["On_Time_Flag"] = on_time_flag
    log["trips_missing_on_time_flag"] = int(pd.isna(df["On_Time_Flag"]).sum())

    # --- transit-time measures ---
    df["Planned_Transit_Hours"] = (df["Planned_ETA"] - df["trip_start_date"]).dt.total_seconds() / 3600
    df["Actual_Transit_Hours"] = (df["actual_eta"] - df["trip_start_date"]).dt.total_seconds() / 3600

    # --- data-quality flags (kept, not silently dropped, per governance practice) ---
    df["Has_Missing_Distance"] = df["TRANSPORTATION_DISTANCE_IN_KM"].isna().astype(int)
    df["Has_Missing_Vehicle_Type"] = df["vehicleType"].isna().astype(int)
    log["rows_missing_distance"] = int(df["Has_Missing_Distance"].sum())
    log["rows_missing_vehicle_type"] = int(df["Has_Missing_Vehicle_Type"].sum())

    log["rows_after_cleaning"] = len(df)
    return df, log


# ----------------------------------------------------------------------
# LOAD
# ----------------------------------------------------------------------
def load(df: pd.DataFrame, log: dict):
    """Assign surrogate keys to every dimension in pandas (avoids any
    ambiguity from SQL joins on natural keys that aren't perfectly
    clean), then bulk-load the dimension and fact tables that the
    01_schema.sql DDL defines."""
    CLEAN_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV_PATH, index=False)
    df = df.copy()

    # --- Dim_Date ---
    all_dates = pd.concat(
        [df["trip_start_date"], df["trip_end_date"], df["Planned_ETA"], df["actual_eta"]]
    ).dropna()
    dmin, dmax = all_dates.min().normalize(), all_dates.max().normalize()
    dim_date = pd.DataFrame({"Full_Date": pd.date_range(dmin, dmax, freq="D")})
    dim_date["Date_Key"] = dim_date["Full_Date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["Year"] = dim_date["Full_Date"].dt.year
    dim_date["Quarter"] = dim_date["Full_Date"].dt.quarter
    dim_date["Month"] = dim_date["Full_Date"].dt.month
    dim_date["Month_Name"] = dim_date["Full_Date"].dt.strftime("%B")
    dim_date["Week_Of_Year"] = dim_date["Full_Date"].dt.isocalendar().week.astype(int)
    dim_date["Day_Of_Week"] = dim_date["Full_Date"].dt.strftime("%A")
    dim_date["Is_Weekend"] = dim_date["Day_Of_Week"].isin(["Saturday", "Sunday"]).astype(int)
    dim_date["Full_Date"] = dim_date["Full_Date"].dt.strftime("%Y-%m-%d")
    dim_date = dim_date[
        ["Date_Key", "Full_Date", "Year", "Quarter", "Month", "Month_Name",
         "Week_Of_Year", "Day_Of_Week", "Is_Weekend"]
    ]
    # Date_Key is keyed off trip_start_date; the couple of rows whose
    # trip_start_date was nulled out as an Excel-epoch artifact fall
    # back to BookingID_Date (the booking creation date) so every trip
    # still lands in the calendar dimension.
    date_basis = df["trip_start_date"].fillna(df["BookingID_Date"])
    log["trips_using_booking_date_fallback_for_date_key"] = int(
        df["trip_start_date"].isna().sum()
    )
    df["Date_Key"] = date_basis.dt.strftime("%Y%m%d")
    df["Date_Key"] = pd.to_numeric(df["Date_Key"], errors="coerce").astype("Int64")

    # --- Dim_Supplier ---
    dim_supplier = (
        df.dropna(subset=["supplierID"])
        .drop_duplicates(subset="supplierID")[["supplierID", "supplierNameCode"]]
        .rename(columns={"supplierID": "Supplier_ID", "supplierNameCode": "Supplier_Name"})
        .reset_index(drop=True)
    )
    dim_supplier.insert(0, "Supplier_Key", dim_supplier.index + 1)
    df = df.merge(dim_supplier[["Supplier_ID", "Supplier_Key"]], left_on="supplierID", right_on="Supplier_ID", how="left")

    # --- Dim_Customer ---
    dim_customer = (
        df.dropna(subset=["customerID"])
        .drop_duplicates(subset="customerID")[["customerID", "customerNameCode"]]
        .rename(columns={"customerID": "Customer_ID", "customerNameCode": "Customer_Name"})
        .reset_index(drop=True)
    )
    dim_customer.insert(0, "Customer_Key", dim_customer.index + 1)
    df = df.merge(dim_customer[["Customer_ID", "Customer_Key"]], left_on="customerID", right_on="Customer_ID", how="left")

    # --- Dim_Vehicle (one row per physical vehicle; see transform()) ---
    dim_vehicle = (
        df.dropna(subset=["vehicle_no"])
        .drop_duplicates(subset="vehicle_no")[["vehicle_no", "vehicleType_canonical", "Vehicle_Type_Clean", "Vehicle_Category"]]
        .rename(columns={"vehicle_no": "Vehicle_No", "vehicleType_canonical": "Vehicle_Type_Raw"})
        .reset_index(drop=True)
    )
    dim_vehicle.insert(0, "Vehicle_Key", dim_vehicle.index + 1)
    df = df.merge(dim_vehicle[["Vehicle_No", "Vehicle_Key"]], left_on="vehicle_no", right_on="Vehicle_No", how="left")

    # --- Dim_GPS_Provider ---
    dim_gps = pd.DataFrame({"Provider_Name": sorted(df["GPS_Provider_Clean"].dropna().unique())})
    dim_gps.insert(0, "GPS_Provider_Key", dim_gps.index + 1)
    df = df.merge(dim_gps, left_on="GPS_Provider_Clean", right_on="Provider_Name", how="left")

    # --- Dim_Location (union of origin + destination City/State pairs) ---
    origin_pairs = df[["Origin_City", "Origin_State"]].rename(columns={"Origin_City": "City", "Origin_State": "State"})
    dest_pairs = df[["Dest_City", "Dest_State"]].rename(columns={"Dest_City": "City", "Dest_State": "State"})
    all_pairs = pd.concat([origin_pairs, dest_pairs], ignore_index=True)
    dim_location = all_pairs.dropna(subset=["State"]).drop_duplicates(subset=["City", "State"], keep="first").reset_index(drop=True)
    dim_location.insert(0, "Location_Key", dim_location.index + 1)

    # merge is NaN-safe for the City column because pandas treats matching
    # NaNs as equal when both join keys are NaN in an ordinary merge only
    # if we fill them first — so fill City NaN with a sentinel for the join.
    sentinel = "__NONE__"
    loc_lookup = dim_location.copy()
    loc_lookup["City_join"] = loc_lookup["City"].fillna(sentinel)
    df["Origin_City_join"] = df["Origin_City"].fillna(sentinel)
    df["Dest_City_join"] = df["Dest_City"].fillna(sentinel)

    df = df.merge(
        loc_lookup[["City_join", "State", "Location_Key"]].rename(columns={"Location_Key": "Origin_Location_Key"}),
        left_on=["Origin_City_join", "Origin_State"], right_on=["City_join", "State"], how="left", suffixes=("", "_oloc"),
    )
    df = df.merge(
        loc_lookup[["City_join", "State", "Location_Key"]].rename(columns={"Location_Key": "Destination_Location_Key"}),
        left_on=["Dest_City_join", "Dest_State"], right_on=["City_join", "State"], how="left", suffixes=("", "_dloc"),
    )
    dim_location = dim_location.drop(columns=[])  # City may legitimately be NULL in the loaded table

    # --- sanity check: the surrogate-key merges must not change row count ---
    log["fact_row_count_before_key_merges"] = log["rows_after_cleaning"]
    log["fact_row_count_after_key_merges"] = len(df)
    if len(df) != log["rows_after_cleaning"]:
        raise RuntimeError("Surrogate-key lookup merge produced a fan-out — investigate dimension uniqueness.")

    df["Market_Type"] = df["Market/Regular "]
    fact = df[[
        "BookingID", "Date_Key", "Supplier_Key", "Customer_Key", "Vehicle_Key",
        "Origin_Location_Key", "Destination_Location_Key", "GPS_Provider_Key",
        "Market_Type", "trip_start_date", "trip_end_date", "Planned_ETA", "actual_eta",
        "TRANSPORTATION_DISTANCE_IN_KM", "Minimum_kms_to_be_covered_in_a_day",
        "Planned_Transit_Hours", "Actual_Transit_Hours", "Delay_Hours", "On_Time_Flag",
        "Raw_Status_Flag", "Status_Match", "Has_Missing_Distance", "Has_Missing_Vehicle_Type",
    ]].rename(columns={
        "BookingID": "Booking_ID",
        "trip_start_date": "Trip_Start_Date",
        "trip_end_date": "Trip_End_Date",
        "Planned_ETA": "Planned_ETA",
        "actual_eta": "Actual_ETA",
        "TRANSPORTATION_DISTANCE_IN_KM": "Distance_KM",
        "Minimum_kms_to_be_covered_in_a_day": "Min_KM_Per_Day",
    })

    # --- build the SQLite database on local disk, then copy it out ---
    if BUILD_DB_PATH.exists():
        BUILD_DB_PATH.unlink()
    conn = sqlite3.connect(BUILD_DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    dim_date.to_sql("Dim_Date", conn, if_exists="append", index=False)
    dim_supplier[["Supplier_Key", "Supplier_ID", "Supplier_Name"]].to_sql("Dim_Supplier", conn, if_exists="append", index=False)
    dim_customer[["Customer_Key", "Customer_ID", "Customer_Name"]].to_sql("Dim_Customer", conn, if_exists="append", index=False)
    dim_vehicle[["Vehicle_Key", "Vehicle_No", "Vehicle_Type_Raw", "Vehicle_Type_Clean", "Vehicle_Category"]].to_sql(
        "Dim_Vehicle", conn, if_exists="append", index=False
    )
    dim_location[["Location_Key", "City", "State"]].to_sql("Dim_Location", conn, if_exists="append", index=False)
    dim_gps[["GPS_Provider_Key", "Provider_Name"]].to_sql("Dim_GPS_Provider", conn, if_exists="append", index=False)
    fact.to_sql("Fact_Trips", conn, if_exists="append", index=False)
    conn.commit()

    cur = conn.cursor()
    log["dim_date_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_Date").fetchone()[0]
    log["dim_supplier_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_Supplier").fetchone()[0]
    log["dim_customer_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_Customer").fetchone()[0]
    log["dim_vehicle_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_Vehicle").fetchone()[0]
    log["dim_location_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_Location").fetchone()[0]
    log["dim_gps_provider_rows"] = cur.execute("SELECT COUNT(*) FROM Dim_GPS_Provider").fetchone()[0]
    log["fact_trips_rows"] = cur.execute("SELECT COUNT(*) FROM Fact_Trips").fetchone()[0]
    log["fact_trips_unmatched_origin"] = cur.execute(
        "SELECT COUNT(*) FROM Fact_Trips WHERE Origin_Location_Key IS NULL"
    ).fetchone()[0]
    log["fact_trips_unmatched_destination"] = cur.execute(
        "SELECT COUNT(*) FROM Fact_Trips WHERE Destination_Location_Key IS NULL"
    ).fetchone()[0]
    conn.close()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD_DB_PATH, DB_PATH)
    return log


# ----------------------------------------------------------------------
# Tableau-ready flattened extract
# ----------------------------------------------------------------------
def export_tableau_extract():
    conn = sqlite3.connect(BUILD_DB_PATH)
    query = """
        SELECT
            f.Booking_ID,
            dt.Full_Date          AS Trip_Date,
            dt.Year, dt.Quarter, dt.Month, dt.Month_Name, dt.Day_Of_Week, dt.Is_Weekend,
            sup.Supplier_Name     AS Carrier,
            cust.Customer_Name    AS Customer,
            veh.Vehicle_No, veh.Vehicle_Type_Clean, veh.Vehicle_Category,
            oloc.City AS Origin_City, oloc.State AS Origin_State,
            dloc.City AS Destination_City, dloc.State AS Destination_State,
            gps.Provider_Name     AS GPS_Provider,
            f.Market_Type,
            f.Distance_KM,
            f.Planned_Transit_Hours,
            f.Actual_Transit_Hours,
            f.Delay_Hours,
            f.On_Time_Flag,
            f.Has_Missing_Distance,
            f.Has_Missing_Vehicle_Type
        FROM Fact_Trips f
        LEFT JOIN Dim_Date dt ON f.Date_Key = dt.Date_Key
        LEFT JOIN Dim_Supplier sup ON f.Supplier_Key = sup.Supplier_Key
        LEFT JOIN Dim_Customer cust ON f.Customer_Key = cust.Customer_Key
        LEFT JOIN Dim_Vehicle veh ON f.Vehicle_Key = veh.Vehicle_Key
        LEFT JOIN Dim_Location oloc ON f.Origin_Location_Key = oloc.Location_Key
        LEFT JOIN Dim_Location dloc ON f.Destination_Location_Key = dloc.Location_Key
        LEFT JOIN Dim_GPS_Provider gps ON f.GPS_Provider_Key = gps.GPS_Provider_Key
    """
    flat = pd.read_sql_query(query, conn)
    conn.close()
    TABLEAU_EXTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    flat.to_csv(TABLEAU_EXTRACT_PATH, index=False)
    return len(flat)


def main():
    df = extract()
    df, log = transform(df)
    log = load(df, log)
    log["tableau_extract_rows"] = export_tableau_extract()

    lines = ["ETL RUN SUMMARY", "=" * 40]
    for k, v in log.items():
        lines.append(f"{k:45s}: {v}")
    report = "\n".join(lines)
    print(report)
    ETL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ETL_LOG_PATH.write_text(report + "\n")


if __name__ == "__main__":
    main()
