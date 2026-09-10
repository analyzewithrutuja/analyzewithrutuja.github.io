-- ============================================================
-- Freight Logistics Data Warehouse — BI Analysis Queries
-- Run against output/trucking_dw.db
-- ============================================================

-- 1) Overall on-time delivery rate
-- (On_Time_Flag is NULL for the 14 trips where neither the ETA
--  timestamps nor the raw status code were populated)
SELECT
    ROUND(AVG(On_Time_Flag) * 100.0, 1) AS on_time_pct,
    COUNT(*) AS trips_with_known_status
FROM Fact_Trips
WHERE On_Time_Flag IS NOT NULL;


-- 2) On-time delivery rate trend by month
SELECT
    d.Year,
    d.Month,
    d.Month_Name,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct
FROM Fact_Trips f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
WHERE f.On_Time_Flag IS NOT NULL
GROUP BY d.Year, d.Month
ORDER BY d.Year, d.Month;


-- 3) Carrier ("supplier") scorecard — volume, on-time rate, avg delay
--    Only carriers with a meaningful sample size are ranked.
SELECT
    sup.Supplier_Name,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct,
    ROUND(AVG(f.Delay_Hours), 1) AS avg_delay_hours
FROM Fact_Trips f
JOIN Dim_Supplier sup ON f.Supplier_Key = sup.Supplier_Key
WHERE f.On_Time_Flag IS NOT NULL
GROUP BY sup.Supplier_Name
HAVING COUNT(*) >= 30
ORDER BY on_time_pct DESC;


-- 4) Vehicle category performance — on-time rate, avg distance, avg delay
SELECT
    veh.Vehicle_Category,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct,
    ROUND(AVG(f.Distance_KM), 1) AS avg_distance_km,
    ROUND(AVG(f.Delay_Hours), 1) AS avg_delay_hours
FROM Fact_Trips f
JOIN Dim_Vehicle veh ON f.Vehicle_Key = veh.Vehicle_Key
GROUP BY veh.Vehicle_Category
ORDER BY trips DESC;


-- 5) Lane (origin state -> destination state) performance —
--    top 15 busiest lanes by trip volume
SELECT
    oloc.State AS origin_state,
    dloc.State AS destination_state,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct,
    ROUND(AVG(f.Distance_KM), 1) AS avg_distance_km
FROM Fact_Trips f
JOIN Dim_Location oloc ON f.Origin_Location_Key = oloc.Location_Key
JOIN Dim_Location dloc ON f.Destination_Location_Key = dloc.Location_Key
GROUP BY oloc.State, dloc.State
ORDER BY trips DESC
LIMIT 15;


-- 6) Top 10 customers (shippers) by trip volume and the on-time
--    service level they actually received
SELECT
    cust.Customer_Name,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct
FROM Fact_Trips f
JOIN Dim_Customer cust ON f.Customer_Key = cust.Customer_Key
GROUP BY cust.Customer_Name
ORDER BY trips DESC
LIMIT 10;


-- 7) Distance vs. delay — do longer hauls run later? (bucketed)
SELECT
    CASE
        WHEN Distance_KM IS NULL THEN 'Unknown'
        WHEN Distance_KM < 100 THEN '0-100 km'
        WHEN Distance_KM < 500 THEN '100-500 km'
        WHEN Distance_KM < 1000 THEN '500-1000 km'
        ELSE '1000+ km'
    END AS distance_band,
    COUNT(*) AS trips,
    ROUND(AVG(On_Time_Flag) * 100.0, 1) AS on_time_pct,
    ROUND(AVG(Delay_Hours), 1) AS avg_delay_hours
FROM Fact_Trips
GROUP BY distance_band
ORDER BY
    CASE distance_band
        WHEN '0-100 km' THEN 1 WHEN '100-500 km' THEN 2
        WHEN '500-1000 km' THEN 3 WHEN '1000+ km' THEN 4 ELSE 5
    END;


-- 8) GPS tracking coverage vs. on-time reporting reliability —
--    are untracked ("Manual/Unknown") trips reported differently?
SELECT
    gps.Provider_Name,
    COUNT(*) AS trips,
    ROUND(AVG(f.On_Time_Flag) * 100.0, 1) AS on_time_pct
FROM Fact_Trips f
JOIN Dim_GPS_Provider gps ON f.GPS_Provider_Key = gps.GPS_Provider_Key
GROUP BY gps.Provider_Name
ORDER BY trips DESC
LIMIT 10;


-- 9) Data-quality summary — counts behind every cleaning decision
--    made in scripts/etl_pipeline.py (see also output/etl_run_log.txt)
SELECT
    (SELECT COUNT(*) FROM Fact_Trips) AS total_trips,
    (SELECT COUNT(*) FROM Fact_Trips WHERE On_Time_Flag IS NULL) AS trips_missing_on_time_flag,
    (SELECT COUNT(*) FROM Fact_Trips WHERE Has_Missing_Distance = 1) AS trips_missing_distance,
    (SELECT COUNT(*) FROM Fact_Trips WHERE Has_Missing_Vehicle_Type = 1) AS trips_missing_vehicle_type,
    (SELECT COUNT(*) FROM Fact_Trips WHERE Status_Match = 0) AS eta_vs_raw_status_mismatches,
    (SELECT COUNT(*) FROM Fact_Trips WHERE Origin_Location_Key IS NULL) AS unmatched_origin,
    (SELECT COUNT(*) FROM Fact_Trips WHERE Destination_Location_Key IS NULL) AS unmatched_destination;
