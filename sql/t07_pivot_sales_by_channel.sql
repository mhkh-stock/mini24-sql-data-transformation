-- t07 — Pivoting with CASE: rows to columns (sales by channel per month)
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: the business wants one row per month with a column per
-- sales channel — Online / In-Store / Phone — so a month can be
-- read across. SQLite has no PIVOT keyword, and the raw channel
-- column holds 11 spellings of 3 channels, so a naive GROUP BY
-- channel would print 11 rows per month.
--
-- QUERY: first clean everything the earlier techniques taught —
-- dedup lines and orders (technique 6), parse the price and the
-- date (techniques 2 and 4), fill the two NULLs by rule
-- (technique 5), normalise the channel spelling (technique 3:
-- strip spaces and hyphens, upper-case, then CASE to the canonical
-- name). Then each column is SUM(CASE WHEN channel = 'X' THEN
-- revenue END), with COALESCE(..., 0) so a month with no sales on
-- a channel honestly shows 0 instead of a blank.
--
-- RETURNS: 6 rows, one per month Jan–Jun 2026.
-- EXPECTED: row totals are the monthly revenue (Jan 37,100 ...
-- Jun 94,200); column totals are the channel totals; grand total
-- PKR 346,800 — the pivot reconciles with the clean mart
-- (technique 10) to the rupee.

WITH catalogue AS (
    SELECT
        product_code,
        CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                             'Rs.', ''), ',', ''), ' ', '')
             AS INTEGER) AS catalogue_price_pkr
    FROM raw_products
),
orders_clean AS (
    SELECT
        order_id,
        CASE
            WHEN order_date_text LIKE '%/%' THEN
                SUBSTR(order_date_text, 7, 4) || '-'
                || SUBSTR(order_date_text, 4, 2) || '-'
                || SUBSTR(order_date_text, 1, 2)
            ELSE order_date_text
        END AS order_date,
        CASE REPLACE(REPLACE(UPPER(TRIM(channel_raw)), ' ', ''), '-', '')
            WHEN 'ONLINE'  THEN 'Online'
            WHEN 'INSTORE' THEN 'In-Store'
            WHEN 'PHONE'   THEN 'Phone'
            ELSE 'UNMAPPED: ' || channel_raw
        END AS channel
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY order_id ORDER BY updated_at DESC) AS rn
        FROM raw_orders
    )
    WHERE rn = 1
),
lines_clean AS (
    SELECT
        li.order_id,
        COALESCE(CAST(NULLIF(TRIM(li.quantity_text), '') AS INTEGER), 1)
            AS quantity,
        COALESCE(
            CAST(REPLACE(REPLACE(REPLACE(
                     NULLIF(TRIM(li.unit_price_text), ''),
                     'Rs.', ''), ',', ''), ' ', '') AS INTEGER),
            c.catalogue_price_pkr) AS unit_price_pkr
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY line_id ORDER BY updated_at DESC) AS rn
        FROM raw_order_items
    ) AS li
    JOIN catalogue AS c ON c.product_code = li.product_code
    WHERE rn = 1
),
monthly_channel AS (
    SELECT
        strftime('%Y-%m', o.order_date) AS month,
        o.channel,
        SUM(l.quantity * l.unit_price_pkr) AS revenue_pkr,
        COUNT(DISTINCT o.order_id) AS orders
    FROM orders_clean AS o
    JOIN lines_clean AS l ON l.order_id = o.order_id
    GROUP BY month, o.channel
)
SELECT
    month,
    COALESCE(SUM(CASE WHEN channel = 'Online' THEN revenue_pkr END), 0)
        AS online_pkr,
    COALESCE(SUM(CASE WHEN channel = 'In-Store' THEN revenue_pkr END), 0)
        AS in_store_pkr,
    COALESCE(SUM(CASE WHEN channel = 'Phone' THEN revenue_pkr END), 0)
        AS phone_pkr,
    SUM(revenue_pkr) AS total_pkr,
    SUM(orders) AS orders
FROM monthly_channel
GROUP BY month
ORDER BY month;
