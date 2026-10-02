-- Music Royalty Statement Pipeline — analysis queries against output/royalty_dw.db

-- 1. Statement processing status: what came in, what loaded, what needs a human
SELECT distributor,
       COUNT(*)                                          AS statements,
       SUM(rows_in)                                      AS lines_in,
       SUM(rows_loaded)                                  AS lines_loaded,
       SUM(rows_quarantined)                             AS lines_quarantined,
       SUM(CASE WHEN status = 'AUTO-PASS' THEN 1 ELSE 0 END) AS auto_pass,
       SUM(CASE WHEN status = 'REVIEW'    THEN 1 ELSE 0 END) AS needs_review,
       SUM(CASE WHEN status = 'REJECTED'  THEN 1 ELSE 0 END) AS rejected
FROM statement_register
GROUP BY distributor;

-- 2. Exception queue, most severe first
SELECT severity, check_name, statement_file, rows_affected, detail
FROM validation_exception
ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, check_name, statement_file;

-- 3. Monthly net earnings per distributor, normalized per chart week
--    (months hold 4 or 5 weekly charts, so raw monthly totals are not comparable)
SELECT f.sale_period,
       f.distributor,
       ROUND(SUM(f.net_usd), 2)                 AS net_usd,
       p.chart_weeks,
       ROUND(SUM(f.net_usd) / p.chart_weeks, 2) AS net_usd_per_chart_week
FROM fact_royalty_line f
JOIN dim_period p ON p.period = f.sale_period
GROUP BY f.sale_period, f.distributor
ORDER BY f.sale_period, f.distributor;

-- 4. Earnings by market tier: where streams come from vs. where money comes from
SELECT t.tier,
       ROUND(100.0 * SUM(f.streams) / (SELECT SUM(streams) FROM fact_royalty_line WHERE is_adjustment = 0), 1) AS pct_streams,
       ROUND(100.0 * SUM(f.net_usd) / (SELECT SUM(net_usd) FROM fact_royalty_line WHERE is_adjustment = 0), 1) AS pct_net_usd
FROM fact_royalty_line f
JOIN dim_territory t ON t.iso2 = f.territory_iso2
WHERE f.is_adjustment = 0
GROUP BY t.tier
ORDER BY t.tier;

-- 5. Top 10 artist catalogs, Jan-Sep (Oct is a partial month)
SELECT d.artist,
       COUNT(DISTINCT f.song_id)  AS songs,
       ROUND(SUM(f.net_usd), 2)   AS net_usd
FROM fact_royalty_line f
JOIN (SELECT DISTINCT song_id, artist FROM dim_track) d ON d.song_id = f.song_id
WHERE f.sale_period <= '2019-09'
GROUP BY d.artist
ORDER BY net_usd DESC
LIMIT 10;

-- 6. Adjustments: every reversal / chargeback and the original line it reverses
SELECT a.statement_file, a.sale_period, a.track_id, a.territory_iso2, a.streams, ROUND(a.net_usd, 2) AS net_usd,
       o.statement_file AS original_statement
FROM fact_royalty_line a
LEFT JOIN fact_royalty_line o
       ON o.distributor = a.distributor AND o.sale_period = a.sale_period
      AND o.track_id = a.track_id AND o.territory_iso2 = a.territory_iso2
      AND o.streams = -a.streams AND o.is_adjustment = 0
WHERE a.is_adjustment = 1
ORDER BY a.statement_file;

-- 7. Quarantine summary: money held back until reviewed
SELECT quarantine_reason, distributor, COUNT(*) AS lines, SUM(streams) AS streams,
       ROUND(SUM(net_local), 2) AS net_local, currency
FROM quarantine_line
GROUP BY quarantine_reason, distributor, currency;
