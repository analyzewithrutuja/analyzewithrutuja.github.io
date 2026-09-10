# Grid Load Dashboard — Build Spec

Source extract: `output/tableau_extract_demand.csv` (one row per zone-hour,
pre-joined with Dim_Date and Dim_Zone — ready to drop into Tableau or Power BI).

## KPI tiles (top row)
- **System Peak Demand (MW)** — MAX(Demand_MW), filterable by zone/date range
- **Average Demand (MW)** — AVG(Demand_MW)
- **YoY Peak Growth %** — this year's peak vs. last year's peak
- **DST-Flagged Hours** — count of Is_DST_Duplicate + Is_Interpolated rows in view (data-quality transparency tile)

## Main trend chart
Line chart: Demand_MW (Y) over Full_Date (X), one line per selected Zone_Code.
Annotate the **2014-01-07 Polar Vortex peak** (49,877 MW, PJME's all-time
January high, ~45% above the January hourly average) as a reference line —
the single clearest illustration of extreme-weather grid stress in the
dataset.

## Zone scorecard (table/heatmap)
Zone_Code | Zone_Name | States_Served | Avg_MW | Peak_MW | % Weekend Discount
— sourced from analysis query 1 and 4. Color-scale the Peak_MW column to
surface which balancing areas run closest to their historical ceiling.

## Daily load-shape chart
Small-multiples line chart: Avg_MW (Y) by Hour_Of_Day (X), faceted by
Zone_Code — shows the classic morning ramp / afternoon-evening peak /
overnight trough pattern used in generation-capacity and demand-response
planning (query 6).

## Seasonal heatmap
Season (rows) x Zone_Code (columns), colored by Avg_MW — shows winter
heating load vs. summer cooling load balance per zone (query 3).

## Filters
Date range, Zone_Code (multi-select), Season, Is_Weekend.

## Forecast panel
Actual vs. predicted Demand_MW for the held-out test year (PJME), from
`output/model_results.md` — XGBoost line vs. actual line, with the
4.36% MAPE called out as a KPI tile.

Once built, add the published dashboard link and a screenshot here and to
the portfolio write-up (same pattern as the Freight Logistics project).
