# Energy Grid Load Forecasting & Data Warehouse

An end-to-end data engineering + ML project that turns raw, messy
utility-grid hourly demand feeds into a star-schema data warehouse, a
next-day load forecasting model, and a BI-ready reporting extract — built
to practice the exact workflow a Data Scientist/Analyst on an Energy &
Utilities team runs day to day: take an operational grid feed, clean it,
model it for forecasting, and answer "how much power will this grid need,
and where does demand spike?"

## Why this project

I built this after comparing my resume against an Energy & Utilities-sector
AI/Data Science posting. My background covers ETL, SQL, dashboarding, and
ML modeling, but I had nothing that demonstrated **utility-grid domain**
experience. This project is that gap, closed with a real dataset rather
than a toy one.

## Data source

**PJM Interconnection hourly load data** — real hourly electricity demand
(MW) reported by 10 balancing-authority zones across the PJM footprint (13
U.S. states + D.C.), October 2002 - August 2018 (~999K hourly readings).
Originally published on Kaggle by *robikscube*
([kaggle.com/datasets/robikscube/hourly-energy-consumption](https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption)),
sourced here via a public GitHub mirror
([panambY/Hourly_Energy_Consumption](https://github.com/panambY/Hourly_Energy_Consumption)).
Raw files are kept at `data/raw/*_hourly.csv` (12 files — 10 loaded, 2 kept
for reference only, see below).

Each row (pre-cleaning) is one hour of demand for one balancing area —
American Electric Power, Commonwealth Edison, Dayton Power & Light, Duke
Energy Ohio/Kentucky, Dominion Energy Virginia, Duquesne Light, East
Kentucky Power Cooperative, FirstEnergy, and the PJM East/West aggregates.

## Architecture

```
data/raw/                     12 raw source files (one per zone, hourly MW)
scripts/etl_pipeline.py       Extract -> clean/standardize -> load
scripts/forecast_model.py     feature engineering + model training/comparison
sql/01_schema.sql             star-schema DDL
sql/02_analysis_queries.sql   BI KPI queries
output/energy_dw.db           finished SQLite data warehouse
output/tableau_extract_demand.csv  flattened, Tableau-ready extract
output/dashboard_blueprint.md      dashboard design spec
output/etl_run_log.txt             data-quality log from the last run
output/model_results.md            forecasting model comparison + metrics
```

The pipeline is a hybrid ETL/ELT: cleaning, DST correction, and calendar
dimension-building happen in pandas (Python), then the result is
bulk-loaded into a SQL star schema — the same shape a Data/BI Analyst would
query in Power BI/Tableau against an enterprise grid-operations warehouse.

## Star schema

```
                Dim_Date
                    |
                    |
Dim_Zone -----  Fact_Hourly_Demand
 (balancing        |
  authority)   Hour_Of_Day, Demand_MW,
               Is_DST_Duplicate, Is_Interpolated
```

- **Fact_Hourly_Demand** — one row per (zone, hour). Measures: demand in
  MW, plus two data-quality flags carried through rather than silently
  dropped.
- **Dim_Date** — standard calendar dimension (year, quarter, month,
  day-of-week, weekend flag, season).
- **Dim_Zone** — the 10 PJM balancing-authority zones, with the real
  states each one serves and its parent ISO.

## ETL / data-quality decisions worth calling out

The raw data was messier than it first looked, and each of these was a
real decision, not a formality:

- **DST fall-back duplicate readings.** Every November, the 2 AM hour is
  logged twice (clocks repeat 1-2 AM) with two genuinely different MW
  readings — the meter can't tell which pass through 2 AM each belongs to.
  Both are flagged (`Is_DST_Duplicate`) and the later-recorded reading is
  kept as authoritative, matching PJM's own published convention.
- **DST spring-forward missing hour.** Every March, the 2-3 AM hour is
  skipped entirely (clocks jump forward). Left alone, this breaks the
  24-hour and 168-hour lag features the forecasting model depends on, so
  the gap is linearly interpolated from its neighbors and flagged
  (`Is_Interpolated`) rather than silently filled.
- **Sensor-startup zero artifact.** FirstEnergy's (`FE`) very first
  recorded hour (2011-06-01 01:00, the instant that meter feed activates)
  is logged as exactly 0 MW — not a real demand reading. Nulled and
  interpolated rather than reported as a genuine data point.
- **Superseded legacy feeds excluded.** Two files (`NI`, `PJM_Load`) stop
  reporting on the *exact* date their successor zone starts — `NI`
  (Northern Illinois) ends 2011-01-01, the day `COMED` begins; `PJM_Load`
  ends 2002-01-01, the day `PJME` begins (`PJMW` follows in April 2002).
  These are re-labeled balancing areas, not independent load — keeping
  them would double-count demand already captured by their successor
  zones, so they're excluded from the fact table (raw files kept in
  `data/raw/` for reference, not loaded).

Every decision above is logged with a row count in `output/etl_run_log.txt`
on each run.

## Key finding

The all-time January (winter) peak across the PJM East zone is
**49,877 MW on 2014-01-07 at 7 PM** — during the widely reported "Polar
Vortex" cold-snap event — roughly **45% above** the January hourly average
of 34,343 MW. That's exactly the kind of extreme-weather demand spike a
grid operator plans generation capacity and demand-response programs
around; see `sql/02_analysis_queries.sql` (query 2) to reproduce it.

## Forecasting model

Trained and compared Linear Regression, Random Forest, and XGBoost to
predict hourly demand for the PJME zone one year into the future (strict
time-based train/test split — the final year of data held out, not a
random shuffle, since random splits would leak future information into the
lag features). Features: hour-of-day, day-of-week, weekend flag, month,
season, 24-hour lag, 168-hour (1-week) lag, and trailing 24-hour rolling
average.

| Model | MAPE | RMSE (MW) | R² |
|---|---|---|---|
| Linear Regression | 6.04% | 2,549 | 0.822 |
| Random Forest | 4.81% | 2,062 | 0.884 |
| **XGBoost** | **4.36%** | **1,842** | **0.907** |

Full results in `output/model_results.md`.

## How to run

```bash
cd scripts
python3 etl_pipeline.py
python3 forecast_model.py
```

Requires `pandas`, `numpy`, `scikit-learn`, and `xgboost`
(`pip install pandas numpy scikit-learn xgboost`). Running the ETL script
rebuilds `output/energy_dw.db` and `output/tableau_extract_demand.csv` from
the raw files and reprints the data-quality log; the forecast script
retrains all three models and rewrites `output/model_results.md`.

To explore the warehouse directly:

```bash
sqlite3 output/energy_dw.db < sql/02_analysis_queries.sql
```

## Dashboard

`output/dashboard_blueprint.md` is a full build spec (KPI tiles, trend
chart with the Polar Vortex event annotated, zone scorecard, daily
load-shape small multiples, seasonal heatmap, forecast panel) for turning
`output/tableau_extract_demand.csv` into a Tableau/Power BI dashboard. Once
built, add the published dashboard link and a screenshot here and to the
portfolio write-up.

## Tech stack

Python (pandas, numpy, scikit-learn, XGBoost), SQL (SQLite — star schema
DDL + analysis queries), Tableau/Power BI (reporting layer).
