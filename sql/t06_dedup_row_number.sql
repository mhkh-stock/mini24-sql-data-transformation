-- t06 — Dedup with ROW_NUMBER(): keep the latest record per key
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: the source re-sends rows. raw_customers has 15 rows for
-- 12 customers (CUST-001, CUST-003 and CUST-007 each appear twice),
-- raw_orders has 34 rows for 32 orders, raw_order_items 54 rows for
-- 52 lines. Counting the raw tables double-counts customers and
-- inflates revenue; DISTINCT cannot help, because the duplicate
-- rows differ (older name spelling, older city, older updated_at).
--
-- QUERY: ROW_NUMBER() OVER (PARTITION BY customer_code
-- ORDER BY updated_at DESC) numbers each customer's rows newest
-- first; keeping rn = 1 keeps exactly the latest version of each
-- customer. The same pattern, with a different PARTITION BY key,
-- dedups orders (by order_id) and lines (by line_id) — the full
-- pipeline in technique 10 uses all three.
--
-- RETURNS: 12 rows — one per customer, the latest version of each.
-- EXPECTED: 15 raw rows -> 12 kept; CUST-001 keeps "Ayesha Khan"
-- (updated 2026-03-10, not the "  ayesha khan" row of 2026-01-05);
-- CUST-003 keeps "Fatima Noor", city Islamabad (2026-04-02, not the
-- blank-city row of 2026-02-01); CUST-007 keeps "Maryam Siddiqui"
-- (2026-03-20).

SELECT
    customer_code,
    name,
    city,
    signup_date_text,
    email,
    updated_at
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_code
            ORDER BY updated_at DESC
        ) AS rn
    FROM raw_customers
)
WHERE rn = 1
ORDER BY customer_code;
