"""
Promotion Impact & Causal Analysis — ETL pipeline
Extract:  Rossmann Store Sales daily data (train.csv, 1,017,209 rows) +
          store metadata (store.csv, 1,115 stores)
Transform: drop closed-store non-days, flag reporting anomalies, standardize
           holiday encoding, build calendar + store dimensions
Load:     star-schema SQLite warehouse (Fact_Daily_Sales, Dim_Date, Dim_Store)

Source: Rossmann Store Sales (Kaggle competition, kaggle.com/c/rossmann-store-sales),
mirrored (no Kaggle auth required) at github.com/dmi3kno/Kaggle-Rossmann.
"""
import pandas as pd
import numpy as np
import sqlite3
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "sql")
DB_PATH = os.path.join(OUTPUT_DIR, "promotion_dw.db")

STATE_HOLIDAY_MAP = {"0": "None", "a": "Public", "b": "Easter", "c": "Christmas"}


def log(lines, msg):
    print(msg)
    lines.append(msg)


def load_and_clean_sales(log_lines):
    df = pd.read_csv(os.path.join(RAW_DIR, "train.csv"),
                      dtype={"StateHoliday": str})
    raw_rows = len(df)
    log(log_lines, f"[Sales] raw_rows={raw_rows}")

    # --- Data-quality decision 1: closed-store non-days ---
    # Open=0 rows are days the store did not trade at all (172,817 of them,
    # ~17% of the file) — Sales is 0 by definition on every one of them.
    # They carry no information about promo effect on sales and would just
    # dilute both the hypothesis test and the causal model with structural
    # zeros, so they're excluded from the fact table entirely (this matches
    # how the Rossmann competition itself scores results — Open=0 days are
    # excluded from evaluation).
    closed_mask = df["Open"] == 0
    n_closed = int(closed_mask.sum())
    df = df.loc[~closed_mask].copy()

    # --- Data-quality decision 2: open-but-zero-sales anomaly ---
    # 54 rows have Open=1 but Sales=0 — a store marked as trading that
    # reported zero revenue for the day (likely a register/reporting
    # glitch, or a partial-day closure not reflected in the Open flag).
    # Rather than silently drop or silently keep them as if they were
    # ordinary observations, they're flagged (Is_Sales_Anomaly) and kept —
    # they're excluded from the causal/statistical analysis scripts but
    # remain in the warehouse for auditability.
    anomaly_mask = (df["Sales"] == 0) & (df["Open"] == 1)
    n_anomaly = int(anomaly_mask.sum())
    df["Is_Sales_Anomaly"] = anomaly_mask.astype(int)

    # --- Data-quality decision 3: StateHoliday encoding ---
    # Raw values are '0' (none), 'a' (public holiday), 'b' (Easter),
    # 'c' (Christmas) — stored as a string with '0' meaning "not a holiday",
    # easy to misread as falsy-but-present. Standardized into a readable
    # category plus an explicit boolean flag.
    df["StateHoliday"] = df["StateHoliday"].fillna("0").replace({0: "0"}).astype(str)
    df["State_Holiday_Type"] = df["StateHoliday"].map(STATE_HOLIDAY_MAP).fillna("None")
    df["Is_State_Holiday"] = (df["State_Holiday_Type"] != "None").astype(int)

    log(log_lines, f"[Sales] closed_store_rows_excluded={n_closed} "
                    f"open_but_zero_sales_anomalies_flagged={n_anomaly} "
                    f"final_rows={len(df)}")
    return df


def load_and_clean_store(log_lines):
    store = pd.read_csv(os.path.join(RAW_DIR, "store.csv"))
    raw_rows = len(store)

    # --- Data-quality decision 4: missing CompetitionDistance ---
    # 3 of 1,115 stores have no recorded distance to the nearest competitor.
    # Imputed with the max observed distance (75,860m) as a "no known
    # nearby competitor" proxy rather than the mean, which would understate
    # how isolated these particular stores actually are; flagged so the
    # imputation is traceable rather than indistinguishable from a real
    # measurement.
    dist_missing = store["CompetitionDistance"].isna()
    n_dist_missing = int(dist_missing.sum())
    max_dist = store["CompetitionDistance"].max()
    store["Is_Competition_Distance_Imputed"] = dist_missing.astype(int)
    store["CompetitionDistance"] = store["CompetitionDistance"].fillna(max_dist)

    # --- Data-quality decision 5: CompetitionOpenSince / Promo2Since fields ---
    # CompetitionOpenSinceMonth/Year is null for 354 stores (competitor
    # open-date simply was never recorded) and Promo2SinceWeek/Year/Interval
    # is null for 544 stores — but that second set of nulls isn't missing
    # data at all: Promo2=0 for those stores by construction (they never
    # enrolled in the continuing loyalty-promo program), so there's no
    # enrollment date to have. Neither is imputed — inventing a fake
    # competitor-open date or Promo2 enrollment date would introduce
    # precision that doesn't exist, and this project's causal model doesn't
    # depend on either field.
    n_comp_open_missing = int(store["CompetitionOpenSinceMonth"].isna().sum())
    n_promo2_missing = int(store["Promo2SinceWeek"].isna().sum())

    log(log_lines, f"[Store] raw_rows={raw_rows} "
                    f"competition_distance_missing_imputed={n_dist_missing} "
                    f"competition_open_date_missing_left_null={n_comp_open_missing} "
                    f"promo2_fields_null_by_design(Promo2=0)={n_promo2_missing}")
    return store


def build_dim_date(sales_df, log_lines):
    dates = pd.DataFrame({"Full_Date": pd.to_datetime(sorted(sales_df["Date"].unique()))})
    dates["Date_Key"] = dates["Full_Date"].dt.strftime("%Y%m%d").astype(int)
    dates["Year"] = dates["Full_Date"].dt.year
    dates["Month"] = dates["Full_Date"].dt.month
    dates["Month_Name"] = dates["Full_Date"].dt.strftime("%B")
    dates["Year_Month"] = dates["Full_Date"].dt.strftime("%Y-%m")
    dates["Day"] = dates["Full_Date"].dt.day
    dates["Day_Of_Week"] = dates["Full_Date"].dt.isocalendar().day.astype(int)  # 1=Mon..7=Sun
    dates["Day_Name"] = dates["Full_Date"].dt.strftime("%A")
    dates["Is_Weekend"] = dates["Day_Of_Week"].isin([6, 7]).astype(int)

    # State holiday type and "any store reports a school holiday" are
    # date-level attributes derived from the sales file (they can vary
    # slightly by store/region in the raw data, so the date dimension takes
    # the modal/most-common value observed across stores for that date).
    holiday_by_date = sales_df.groupby("Date").agg(
        State_Holiday_Type=("State_Holiday_Type", lambda s: s.mode().iat[0]),
        Is_State_Holiday=("Is_State_Holiday", "max"),
        Is_School_Holiday_Any=("SchoolHoliday", "max"),
    ).reset_index()
    dates["Date_Str"] = dates["Full_Date"].dt.strftime("%Y-%m-%d")
    dates = dates.merge(holiday_by_date, left_on="Date_Str", right_on="Date", how="left")

    dates["Full_Date"] = dates["Date_Str"]
    log(log_lines, f"[Dim_Date] {len(dates)} calendar days built "
                    f"({dates['Full_Date'].min()} to {dates['Full_Date'].max()})")
    return dates[["Date_Key", "Full_Date", "Year", "Month", "Month_Name", "Year_Month",
                  "Day", "Day_Of_Week", "Day_Name", "Is_Weekend",
                  "State_Holiday_Type", "Is_State_Holiday", "Is_School_Holiday_Any"]]


def main():
    log_lines = []
    log(log_lines, "=== Promotion Impact & Causal Analysis ETL run ===")

    sales = load_and_clean_sales(log_lines)
    store = load_and_clean_store(log_lines)
    dim_date = build_dim_date(sales, log_lines)

    dim_store = store.rename(columns={
        "Store": "Store_Key",
        "StoreType": "Store_Type",
        "Assortment": "Assortment",
        "CompetitionDistance": "Competition_Distance_M",
        "CompetitionOpenSinceMonth": "Competition_Open_Since_Month",
        "CompetitionOpenSinceYear": "Competition_Open_Since_Year",
        "Promo2": "Has_Promo2",
        "Promo2SinceWeek": "Promo2_Since_Week",
        "Promo2SinceYear": "Promo2_Since_Year",
        "PromoInterval": "Promo2_Interval",
    })[["Store_Key", "Store_Type", "Assortment", "Competition_Distance_M",
        "Is_Competition_Distance_Imputed", "Competition_Open_Since_Month",
        "Competition_Open_Since_Year", "Has_Promo2", "Promo2_Since_Week",
        "Promo2_Since_Year", "Promo2_Interval"]]

    fact = sales.copy()
    fact["Date_Key"] = pd.to_datetime(fact["Date"]).dt.strftime("%Y%m%d").astype(int)
    fact = fact.rename(columns={"Store": "Store_Key", "SchoolHoliday": "School_Holiday"})
    fact = fact[["Date_Key", "Store_Key", "Sales", "Customers", "Promo",
                 "School_Holiday", "Is_Sales_Anomaly"]]

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fact.to_csv(os.path.join(PROCESSED_DIR, "fact_daily_sales_cleaned.csv"), index=False)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(os.path.join(SQL_DIR, "01_schema.sql")) as f:
        conn.executescript(f.read())
    dim_date.to_sql("Dim_Date", conn, if_exists="append", index=False)
    dim_store.to_sql("Dim_Store", conn, if_exists="append", index=False)
    fact.to_sql("Fact_Daily_Sales", conn, if_exists="append", index=False)
    conn.commit()

    log(log_lines, f"[Load] Fact_Daily_Sales: {len(fact):,} rows | "
                    f"Dim_Date: {len(dim_date):,} rows | Dim_Store: {len(dim_store):,} rows")
    log(log_lines, f"[Load] SQLite warehouse written to {os.path.abspath(DB_PATH)}")

    conn.close()

    with open(os.path.join(OUTPUT_DIR, "etl_run_log.txt"), "w") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    main()
