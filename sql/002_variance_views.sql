CREATE OR REPLACE VIEW daily_variance AS
SELECT
    f.date,
    f.location_id,
    l.name AS location_name,
    f.projected_revenue,
    a.actual_revenue,
    ROUND(a.actual_revenue - f.projected_revenue, 2) AS revenue_variance,
    ROUND(
        ((a.actual_revenue - f.projected_revenue) / NULLIF(f.projected_revenue, 0)) * 100,
        2
    ) AS revenue_variance_pct,
    f.projected_attendance,
    a.actual_attendance,
    (a.actual_attendance - f.projected_attendance) AS attendance_variance,
    ROUND(
        ((a.actual_attendance - f.projected_attendance)::NUMERIC
            / NULLIF(f.projected_attendance, 0)) * 100,
        2
    ) AS attendance_variance_pct
FROM daily_flash f
JOIN daily_actuals a
    ON f.date = a.date AND f.location_id = a.location_id
JOIN locations l
    ON l.id = f.location_id;

CREATE OR REPLACE VIEW flagged_anomalies AS
SELECT
    date,
    location_id,
    location_name,
    projected_revenue,
    actual_revenue,
    revenue_variance,
    revenue_variance_pct,
    CASE
        WHEN revenue_variance_pct >= 15 THEN 'over_projection'
        WHEN revenue_variance_pct <= -15 THEN 'under_projection'
    END AS anomaly_type
FROM daily_variance
WHERE ABS(revenue_variance_pct) >= 15
ORDER BY date DESC;
