# Tableau Dashboard Blueprint — Freight On-Time Performance

**Data source:** `output/tableau_extract_trips.csv` (one row per trip, already
denormalized — connect Tableau directly to this file; no joins needed).

## Field notes for Tableau

| Field | Type to set in Tableau | Notes |
|---|---|---|
| `On_Time_Flag` | Measure (keep numeric 0/1) | Build a calculated field `On-Time %` = `AVG([On_Time_Flag])`, format as percentage. Rows where it's blank (14 trips) should be excluded automatically since AVG ignores nulls. |
| `Trip_Date` | Dimension → Date | Drives the monthly trend line. |
| `Delay_Hours` | Measure | Positive = late, negative = early/on-time. |
| `Distance_KM`, `Has_Missing_Distance` | Measure / flag | Filter `Has_Missing_Distance = 0` before any distance-based average so the 712 trips with no recorded distance don't skew it. |
| `Vehicle_Type_Clean`, `Has_Missing_Vehicle_Type` | Dimension / flag | Same treatment as distance for vehicle-based views. |
| `Carrier`, `Customer`, `Vehicle_Category`, `Origin_State`, `Destination_State`, `GPS_Provider` | Dimensions | Used as filters/breakdowns below. |

## Layout — one dashboard, four zones

**1. KPI header strip (top, 4-5 tiles)**
- Overall On-Time % (big number, `AVG([On_Time_Flag])`)
- Total Trips (`COUNTD([Booking_ID])`)
- Avg Delay (hours) — for late trips only (`Delay_Hours > 0`)
- Active Carriers (`COUNTD([Carrier])`)
- Total Distance Covered (km, where `Has_Missing_Distance = 0`)

**2. On-Time % trend over time (top-left, largest panel)**
- Line chart: `Trip_Date` (continuous, by month) on columns, `On-Time %` on rows.
- This is the headline finding in the data: on-time performance was ~99%
  through mid-2019, collapsed to near 0% from roughly July 2019 through
  early 2020, then partially recovered by August 2020. Annotate the
  collapse — it's the kind of pattern a BI Analyst would flag to
  leadership as needing root-cause investigation (e.g., a change in how
  planned ETAs were being set, a capacity constraint, or a demand
  surge) rather than something to explain away in the dashboard itself.

**3. Carrier scorecard (top-right)**
- Horizontal bar chart: `Carrier` (dimension, top 15 by trip count) vs.
  `On-Time %`, colored by on-time % (red-to-green diverging).
  Add trip count as a label so a viewer can see volume alongside rate —
  a carrier with 3 trips and 100% on-time isn't the same signal as one
  with 500 trips at 60%.

**4. Vehicle category & lane breakdown (bottom, split panel)**
- Left: bar chart of `Vehicle_Category` (Trailer / HCV / MCV / LCV /
  Container / Other) by trip count, colored/labeled with `On-Time %`.
- Right: table or highlight table of the top 15 `Origin_State` →
  `Destination_State` lanes by trip volume, with `On-Time %` and
  `Distance_KM` average as additional columns.

## Filters (dashboard-level, apply to all views)
- `Trip_Date` range slider
- `Carrier` (multi-select)
- `Vehicle_Category` (multi-select)
- `Customer` (multi-select)

## Suggested title
"Freight On-Time Performance — Truck Trip Operations Dashboard"

## Build steps
1. Open Tableau (Desktop or Public) → Connect → Text File → select
   `tableau_extract_trips.csv`.
2. Set field types per the table above.
3. Build each of the four views as its own sheet.
4. Assemble into one dashboard using the four-zone layout, add the
   filters, and set them to apply to all four sheets.
5. Export/publish and add the link (and a screenshot) to the project
   README and portfolio page.
