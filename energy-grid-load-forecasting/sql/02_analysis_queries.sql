-- Energy Grid Load Forecasting — BI analysis queries
-- Run against output/energy_dw.db

-- 1. System-wide peak and average demand by zone
SELECT z.Zone_Code, z.Zone_Name, z.States_Served,
       ROUND(AVG(f.Demand_MW), 0) AS Avg_MW,
       MAX(f.Demand_MW) AS Peak_MW,
       COUNT(*) AS Hours_Recorded
FROM Fact_Hourly_Demand f
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
GROUP BY z.Zone_Code
ORDER BY Peak_MW DESC;

-- 2. Key finding: the January 2014 Polar Vortex — record winter peak demand
--    (PJME hits its all-time January high on 2014-01-07, ~45% above the
--     January hourly average, during the widely reported cold-snap event)
SELECT d.Full_Date, f.Hour_Of_Day, f.Demand_MW
FROM Fact_Hourly_Demand f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
WHERE z.Zone_Code = 'PJME' AND d.Month = 1
ORDER BY f.Demand_MW DESC
LIMIT 1;

-- 3. Seasonal demand profile (avg MW by season, system-wide across zones)
SELECT d.Season, ROUND(AVG(f.Demand_MW), 0) AS Avg_MW
FROM Fact_Hourly_Demand f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
GROUP BY d.Season
ORDER BY Avg_MW DESC;

-- 4. Weekday vs. weekend demand (industrial/commercial load signature)
SELECT z.Zone_Code, d.Is_Weekend, ROUND(AVG(f.Demand_MW), 0) AS Avg_MW
FROM Fact_Hourly_Demand f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
GROUP BY z.Zone_Code, d.Is_Weekend
ORDER BY z.Zone_Code, d.Is_Weekend;

-- 5. Year-over-year peak demand trend (system-wide, PJME as bellwether zone)
SELECT d.Year, MAX(f.Demand_MW) AS Peak_MW
FROM Fact_Hourly_Demand f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
WHERE z.Zone_Code = 'PJME'
GROUP BY d.Year
ORDER BY d.Year;

-- 6. Hour-of-day demand curve (daily load shape, for capacity planning)
SELECT z.Zone_Code, f.Hour_Of_Day, ROUND(AVG(f.Demand_MW), 0) AS Avg_MW
FROM Fact_Hourly_Demand f
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
GROUP BY z.Zone_Code, f.Hour_Of_Day
ORDER BY z.Zone_Code, f.Hour_Of_Day;

-- 7. Data-quality audit: DST-flagged rows retained in the warehouse
SELECT z.Zone_Code,
       SUM(f.Is_DST_Duplicate) AS DST_Fallback_Rows,
       SUM(f.Is_Interpolated) AS DST_Springforward_Interpolated_Rows
FROM Fact_Hourly_Demand f
JOIN Dim_Zone z ON f.Zone_Key = z.Zone_Key
GROUP BY z.Zone_Code;
