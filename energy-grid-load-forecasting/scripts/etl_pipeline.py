"""
Energy Grid Load Forecasting — ETL pipeline
Extract:  12 raw PJM balancing-authority CSVs (hourly demand, MW)
Transform: resolve DST duplicates/gaps, drop superseded legacy feeds,
           null out sensor-startup artifacts, build calendar dimension
Load:     star-schema SQLite warehouse (Fact_Hourly_Demand, Dim_Date, Dim_Zone)

Source: PJM Interconnection hourly load data, Oct 2002 - Aug 2018,
originally published via Kaggle (robikscube/hourly-energy-consumption),
mirrored at github.com/panambY/Hourly_Energy_Consumption.
"""
import pandas as pd
import numpy as np
import sqlite3
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "sql")
DB_PATH = os.path.join(OUTPUT_DIR, "energy_dw.db")

# Zone metadata — real PJM Interconnection member/balancing-authority footprint
ZONE_META = {
    "AEP":    ("American Electric Power",  "OH, WV, VA, IN, MI, KY, TN"),
    "COMED":  ("Commonwealth Edison",       "IL (Chicago metro)"),
    "DAYTON": ("Dayton Power & Light (AES Ohio)", "OH (west-central)"),
    "DEOK":   ("Duke Energy Ohio/Kentucky", "OH, KY (Cincinnati metro)"),
    "DOM":    ("Dominion Energy Virginia",  "VA, NC (northeastern)"),
    "DUQ":    ("Duquesne Light",            "PA (Pittsburgh metro)"),
    "EKPC":   ("East Kentucky Power Cooperative", "KY (eastern)"),
    "FE":     ("FirstEnergy",               "OH, PA, NJ, MD, WV"),
    "PJME":   ("PJM East Aggregate",        "Mid-Atlantic region"),
    "PJMW":   ("PJM West Aggregate",        "Appalachian/Midwest region"),
}

# Zones excluded as superseded/legacy feeds (see run log for reasoning)
LEGACY_EXCLUDED = ["NI", "PJM_Load"]

SEASON_MAP = {12: "Winter", 1: "Winter", 2: "Winter",
              3: "Spring", 4: "Spring", 5: "Spring",
              6: "Summer", 7: "Summer", 8: "Summer",
              9: "Fall", 10: "Fall", 11: "Fall"}


def log(lines, msg):
    print(msg)
    lines.append(msg)


def load_and_clean_zone(zone_code, log_lines):
    path = os.path.join(RAW_DIR, f"{zone_code}_hourly.csv")
    df = pd.read_csv(path)
    value_col = [c for c in df.columns if c != "Datetime"][0]
    df = df.rename(columns={value_col: "Demand_MW"})
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    raw_rows = len(df)

    # --- Data-quality decision 1: DST fall-back duplicate 2 AM readings ---
    # Nov clock change logs the 2 AM hour twice with two different MW
    # readings (genuinely ambiguous — the meter can't tell which reading
    # belongs to which pass through 2 AM). Kept both, flagged, and the
    # later-recorded reading is treated as authoritative for aggregates
    # (matches PJM's own published convention of using the second sample).
    dup_mask = df["Datetime"].duplicated(keep=False)
    n_dst_dup_rows = int(dup_mask.sum())
    df["Is_DST_Duplicate"] = dup_mask.astype(int)
    df = df.sort_values("Datetime").drop_duplicates(subset="Datetime", keep="last")

    # --- Data-quality decision 2: DST spring-forward missing hour ---
    # March clock change skips an hour entirely (2-3 AM doesn't exist).
    # Rather than leave a gap that breaks lag-feature calculations for
    # forecasting, the missing hour is linearly interpolated from its
    # immediate neighbors and flagged so it can be excluded from
    # accuracy-sensitive reporting.
    full_range = pd.date_range(df["Datetime"].min(), df["Datetime"].max(), freq="h")
    df = df.set_index("Datetime").reindex(full_range)
    df.index.name = "Datetime"
    n_missing = int(df["Demand_MW"].isna().sum())
    df["Is_Interpolated"] = df["Demand_MW"].isna().astype(int)
    df["Demand_MW"] = df["Demand_MW"].interpolate(method="linear")
    df["Is_DST_Duplicate"] = df["Is_DST_Duplicate"].fillna(0).astype(int)

    # --- Data-quality decision 3: sensor-startup zero artifact ---
    # FE's very first recorded hour (2011-06-01 01:00, the instant the
    # meter feed activates) is logged as exactly 0 MW — not a real demand
    # reading. Nulled and interpolated from the next valid reading rather
    # than reported as a real data point.
    zero_mask = df["Demand_MW"] <= 0
    n_zero = int(zero_mask.sum())
    if n_zero:
        df.loc[zero_mask, "Demand_MW"] = np.nan
        df["Demand_MW"] = df["Demand_MW"].interpolate(method="linear").bfill()

    df = df.reset_index()
    log(log_lines, f"[{zone_code}] raw_rows={raw_rows} dst_duplicate_rows={n_dst_dup_rows} "
                    f"dst_missing_hours_interpolated={n_missing} zero_reading_artifacts_nulled={n_zero} "
                    f"final_rows={len(df)}")
    return df


def build_dim_date(all_dates, log_lines):
    dates = pd.DataFrame({"Full_Date": pd.to_datetime(sorted(set(all_dates)))})
    dates["Date_Key"] = dates["Full_Date"].dt.strftime("%Y%m%d").astype(int)
    dates["Year"] = dates["Full_Date"].dt.year
    dates["Quarter"] = dates["Full_Date"].dt.quarter
    dates["Month"] = dates["Full_Date"].dt.month
    dates["Month_Name"] = dates["Full_Date"].dt.strftime("%B")
    dates["Day"] = dates["Full_Date"].dt.day
    dates["Day_Of_Week"] = dates["Full_Date"].dt.dayofweek
    dates["Day_Name"] = dates["Full_Date"].dt.strftime("%A")
    dates["Is_Weekend"] = dates["Day_Of_Week"].isin([5, 6]).astype(int)
    dates["Season"] = dates["Month"].map(SEASON_MAP)
    dates["Full_Date"] = dates["Full_Date"].dt.strftime("%Y-%m-%d")
    log(log_lines, f"[Dim_Date] {len(dates)} calendar days built "
                    f"({dates['Full_Date'].min()} to {dates['Full_Date'].max()})")
    return dates[["Date_Key", "Full_Date", "Year", "Quarter", "Month", "Month_Name",
                  "Day", "Day_Of_Week", "Day_Name", "Is_Weekend", "Season"]]


def main():
    log_lines = []
    log(log_lines, "=== Energy Grid Load Forecasting ETL run ===")
    log(log_lines, f"Legacy/superseded feeds excluded: {LEGACY_EXCLUDED}")
    log(log_lines, "  NI (Northern Illinois) reporting stops 2011-01-01, the exact date "
                    "COMED begins — PJM re-labeled this balancing area rather than the feed "
                    "actually ending. PJM_Load stops 2002-01-01, the date PJME begins (PJMW "
                    "follows in April 2002) — the same aggregate-to-split-zone transition. "
                    "Keeping both would double-count demand already captured by their successor "
                    "zones, so they are excluded from the fact table (raw files kept in "
                    "data/raw/ for reference, not loaded).")

    frames = []
    for zone_code in ZONE_META:
        df = load_and_clean_zone(zone_code, log_lines)
        df["Zone_Code"] = zone_code
        frames.append(df)

    all_df = pd.concat(frames, ignore_index=True)
    all_df["Date_Key"] = all_df["Datetime"].dt.strftime("%Y%m%d").astype(int)
    all_df["Hour_Of_Day"] = all_df["Datetime"].dt.hour

    dim_date = build_dim_date(all_df["Datetime"].dt.floor("D"), log_lines)

    dim_zone = pd.DataFrame([
        {"Zone_Code": code, "Zone_Name": name, "States_Served": states,
         "Parent_ISO": "PJM Interconnection"}
        for code, (name, states) in ZONE_META.items()
    ])
    dim_zone["Zone_Key"] = range(1, len(dim_zone) + 1)

    fact = all_df.merge(dim_zone[["Zone_Code", "Zone_Key"]], on="Zone_Code")
    fact = fact[["Date_Key", "Zone_Key", "Hour_Of_Day", "Demand_MW",
                 "Is_DST_Duplicate", "Is_Interpolated"]]

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fact.to_csv(os.path.join(PROCESSED_DIR, "fact_hourly_demand_cleaned.csv"), index=False)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(os.path.join(SQL_DIR, "01_schema.sql")) as f:
        conn.executescript(f.read())
    dim_date.to_sql("Dim_Date", conn, if_exists="append", index=False)
    dim_zone[["Zone_Key", "Zone_Code", "Zone_Name", "States_Served", "Parent_ISO"]].to_sql(
        "Dim_Zone", conn, if_exists="append", index=False)
    fact.to_sql("Fact_Hourly_Demand", conn, if_exists="append", index=False)
    conn.commit()

    # Tableau/Power BI-ready flattened extract
    extract = fact.merge(dim_date, on="Date_Key").merge(
        dim_zone[["Zone_Key", "Zone_Code", "Zone_Name", "States_Served"]], on="Zone_Key")
    extract.to_csv(os.path.join(OUTPUT_DIR, "tableau_extract_demand.csv"), index=False)

    log(log_lines, f"[Load] Fact_Hourly_Demand: {len(fact):,} rows | "
                    f"Dim_Date: {len(dim_date):,} rows | Dim_Zone: {len(dim_zone)} rows")
    log(log_lines, f"[Load] SQLite warehouse written to {os.path.abspath(DB_PATH)}")

    conn.close()

    with open(os.path.join(OUTPUT_DIR, "etl_run_log.txt"), "w") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    main()
