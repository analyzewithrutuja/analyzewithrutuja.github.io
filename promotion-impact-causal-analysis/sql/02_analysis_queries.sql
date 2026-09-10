-- Promotion Impact & Causal Analysis — BI analysis queries
-- Run against output/promotion_dw.db

-- 1. Naive promo vs. non-promo comparison (the confounded baseline the
--    causal analysis in causal_analysis.py improves on)
SELECT f.Promo,
       COUNT(*) AS Store_Days,
       ROUND(AVG(f.Sales), 0) AS Avg_Sales,
       ROUND(AVG(f.Customers), 1) AS Avg_Customers
FROM Fact_Daily_Sales f
WHERE f.Is_Sales_Anomaly = 0
GROUP BY f.Promo;

-- 2. Promo frequency and avg sales by store type — shows why raw promo/
--    non-promo comparisons are confounded (promo usage isn't uniform
--    across store types)
SELECT s.Store_Type,
       ROUND(AVG(f.Promo) * 100, 1) AS Pct_Days_On_Promo,
       ROUND(AVG(CASE WHEN f.Promo = 1 THEN f.Sales END), 0) AS Avg_Sales_Promo,
       ROUND(AVG(CASE WHEN f.Promo = 0 THEN f.Sales END), 0) AS Avg_Sales_NonPromo
FROM Fact_Daily_Sales f
JOIN Dim_Store s ON f.Store_Key = s.Store_Key
WHERE f.Is_Sales_Anomaly = 0
GROUP BY s.Store_Type
ORDER BY s.Store_Type;

-- 3. Monthly sales trend, promo vs. non-promo days (the seasonal
--    confound the two-way fixed-effects model controls for)
SELECT d.Year_Month,
       ROUND(AVG(CASE WHEN f.Promo = 1 THEN f.Sales END), 0) AS Avg_Sales_Promo,
       ROUND(AVG(CASE WHEN f.Promo = 0 THEN f.Sales END), 0) AS Avg_Sales_NonPromo
FROM Fact_Daily_Sales f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
WHERE f.Is_Sales_Anomaly = 0
GROUP BY d.Year_Month
ORDER BY d.Year_Month;

-- 4. Day-of-week sales pattern (the calendar confound controlled for
--    in the regression — promo days aren't evenly spread across weekdays)
SELECT d.Day_Name, d.Day_Of_Week,
       ROUND(AVG(f.Promo) * 100, 1) AS Pct_Days_On_Promo,
       ROUND(AVG(f.Sales), 0) AS Avg_Sales
FROM Fact_Daily_Sales f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
WHERE f.Is_Sales_Anomaly = 0
GROUP BY d.Day_Of_Week
ORDER BY d.Day_Of_Week;

-- 5. Top 10 stores by average daily sales (for context / picking
--    representative stores for the seasonal-decomposition view)
SELECT s.Store_Key, s.Store_Type, s.Assortment,
       ROUND(AVG(f.Sales), 0) AS Avg_Sales,
       COUNT(*) AS Days_Open
FROM Fact_Daily_Sales f
JOIN Dim_Store s ON f.Store_Key = s.Store_Key
WHERE f.Is_Sales_Anomaly = 0
GROUP BY s.Store_Key
ORDER BY Avg_Sales DESC
LIMIT 10;

-- 6. State/school holiday sales impact
SELECT d.State_Holiday_Type,
       ROUND(AVG(f.Sales), 0) AS Avg_Sales,
       COUNT(*) AS Store_Days
FROM Fact_Daily_Sales f
JOIN Dim_Date d ON f.Date_Key = d.Date_Key
WHERE f.Is_Sales_Anomaly = 0
GROUP BY d.State_Holiday_Type
ORDER BY Avg_Sales DESC;

-- 7. Data-quality audit: sales anomalies and imputed store fields
SELECT
    (SELECT COUNT(*) FROM Fact_Daily_Sales WHERE Is_Sales_Anomaly = 1) AS Sales_Anomaly_Rows,
    (SELECT COUNT(*) FROM Dim_Store WHERE Is_Competition_Distance_Imputed = 1) AS Stores_With_Imputed_Competition_Distance;
