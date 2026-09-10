# Freight Logistics Data Warehouse & ETL Pipeline

An end-to-end ETL project that turns raw, messy GPS-tracked truck-trip
data into a star-schema data warehouse and a BI-ready reporting extract —
built to practice the exact workflow a Business Intelligence Analyst at a
truckload carrier runs day to day: take an operational data feed, clean
it, model it for reporting, and answer "how's our on-time performance,
and where is it breaking down?"

## Why this project

I built this after comparing my resume against a BI Analyst posting at a
truckload carrier (Knight Transportation). My background covers ETL,
SQL, and dashboarding, but I had nothing that demonstrated a proper
**data warehouse / star-schema** build or **trucking-domain** reporting.
This project is that gap, closed with a real dataset rather than a toy
one.

## Data source

**Delivery Truck Trip Data** — GPS-tracked truck trips for an Indian
auto-parts logistics network (6,880 bookings, March 2019 – December
2020). Originally published on Kaggle by *ramakrishnanthiyagu*
([kaggle.com/datasets/ramakrishnanthiyagu/delivery-truck-trips-data](https://www.kaggle.com/datasets/ramakrishnanthiyagu/delivery-truck-trips-data)),
sourced here via a public GitHub mirror
([Johanklemantan/Delivery-Truck-Ontime-Delay-Prediction](https://github.com/Johanklemantan/Delivery-Truck-Ontime-Delay-Prediction)).
The raw file is kept at `data/raw/delivery_truck_trips_raw.xlsx`.

Each row is one truck trip: booking date, planned vs. actual arrival
time, origin/destination, the transport company ("supplier") running
the trip, the customer (an OEM like Ashok Leyland or Daimler) who
booked it, the vehicle, and its GPS tracking provider.

## Architecture

```
data/raw/               raw source file (Excel)
scripts/etl_pipeline.py Extract -> clean/standardize -> load
sql/01_schema.sql       star-schema DDL
sql/02_analysis_queries.sql   BI KPI queries
output/trucking_dw.db          finished SQLite data warehouse
output/tableau_extract_trips.csv  flattened, Tableau-ready extract
output/dashboard_blueprint.md     dashboard design spec
output/etl_run_log.txt            data-quality log from the last run
```

The pipeline is a hybrid ETL/ELT: cleaning and standardization happen in
pandas (Python), surrogate keys are assigned there too, and the result
is bulk-loaded into a SQL star schema — the same shape a BI Analyst
would query in Power BI/Tableau against an enterprise warehouse.

## Star schema

```
                    Dim_Date
                        |
Dim_Supplier --\        |        /-- Dim_Customer
 (carrier)      \       |       /
                 >-- Fact_Trips --<
                /       |       \
   Dim_Vehicle-/        |        \-- Dim_GPS_Provider
                   Dim_Location
                 (role-played twice:
                  Origin & Destination)
```

- **Fact_Trips** — one row per trip (booking). Measures: distance,
  planned/actual transit hours, delay hours, on-time flag, plus two
  data-quality flags carried through rather than silently dropped.
- **Dim_Date** — standard calendar dimension.
- **Dim_Supplier** — the trucking/transport company running the trip
  (this dataset's "carrier").
- **Dim_Customer** — the shipper who booked the trip.
- **Dim_Vehicle** — one row per physical vehicle, with a cleaned/
  standardized type and a coarse category (Trailer / HCV / MCV / LCV /
  Container).
- **Dim_Location** — City/State, used twice via separate foreign keys
  (Origin and Destination) — a role-playing dimension.
- **Dim_GPS_Provider** — the tracking vendor used for the trip.

## ETL / data-quality decisions worth calling out

The raw data was messier than it first looked, and each of these was a
real decision, not a formality:

- **Excel epoch artifacts.** A handful of timestamp cells were blank
  and Excel serialized them as `1899-12-30` (its date-zero). These are
  nulled out rather than treated as real dates (`excel_epoch_date_artifacts_nulled`
  in the run log).
- **Inconsistent vehicle-type strings.** The same vehicle class was
  logged as `"24 / 26 FT Taurus..."` in some rows and
  `"24 | 26 FT Taurus..."` in others. Normalized via regex before
  bucketing into a `Vehicle_Category`.
- **A vehicle logged under more than one type string.** 46 vehicles
  had inconsistent `vehicleType` values across their trips; resolved to
  the single most-frequently-logged value per vehicle so `Dim_Vehicle`
  holds one row per physical truck.
- **Same customer, inconsistent name casing.** One customer ID
  (`ALLEXCHE45`) appeared as both `"Ashok leyland limited"` and
  `"Ashok Leyland Limited"`. Standardized to title case for every
  customer and supplier name.
- **Location codes don't reliably map 1:1 to a facility.** 52 origin
  codes and 136 destination codes were reused across differently-named
  facilities in the source system, so `Dim_Location` is built at the
  City/State grain instead — the cleanest reliable grain, and also the
  right one for lane-level reporting.
- **Two conflicting on-time signals.** The source has both raw `G`/`R`
  status codes *and* planned/actual ETA timestamps, and they don't
  always agree (18 of 6,875 trips disagree). The ETA timestamps are
  treated as ground truth, with the raw code used only as a fallback
  when timestamps are missing, and the disagreement count is kept as a
  QA metric rather than hidden.
- **Missing distance and vehicle type.** 712 trips have no recorded
  distance and 824 have no vehicle type. These are flagged
  (`Has_Missing_Distance`, `Has_Missing_Vehicle_Type`) and kept in the
  fact table rather than dropped, so downstream reports can decide
  whether to exclude them per-metric instead of losing the trips
  entirely.

Every decision above is also logged with a row count in
`output/etl_run_log.txt` on each run.

## Key finding

Overall on-time delivery across the full dataset is **37.4%** — but
that number hides a dramatic trend: on-time performance ran at **~99%**
from March–June 2019, then collapsed to **near 0%** for an extended
stretch from roughly July 2019 through early 2020, before partially
recovering to **~66%** by August 2020. That's exactly the kind of
pattern a BI Analyst would flag for root-cause investigation (a change
in how planned ETAs were being set? a capacity constraint? a demand
surge?) rather than something to explain away — see
`sql/02_analysis_queries.sql` (query 2) to reproduce it.

## How to run

```bash
cd scripts
python3 etl_pipeline.py
```

Requires `pandas`, `numpy`, and `openpyxl` (`pip install pandas numpy
openpyxl`). Running it rebuilds `output/trucking_dw.db` and
`output/tableau_extract_trips.csv` from the raw file and reprints the
data-quality log.

To explore the warehouse directly:

```bash
sqlite3 output/trucking_dw.db < sql/02_analysis_queries.sql
```

## Dashboard

`output/dashboard_blueprint.md` is a full build spec (KPI tiles, trend
chart, carrier scorecard, vehicle/lane breakdown, filters) for turning
`output/tableau_extract_trips.csv` into a Tableau dashboard. Once built,
add the published dashboard link and a screenshot here and to the
portfolio write-up.

## Tech stack

Python (pandas, numpy, openpyxl), SQL (SQLite — star schema DDL +
analysis queries), Tableau (reporting layer).
