-- t08 — Conditional aggregation: SUM(CASE...) KPIs in one pass
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: the manager wants, per category, revenue split by
-- channel, the average line value, and how many lines were premium
-- (PKR 10,000+) — four questions that naive SQL answers with four
-- separate queries and four scans of the data.
--
-- QUERY: one GROUP BY, many conditional aggregates. SUM(CASE WHEN
-- channel = 'Online' THEN revenue ELSE 0 END) adds only the Online
-- rows; SUM(CASE WHEN revenue >= 10000 THEN 1 ELSE 0 END) counts
-- only the premium lines. The share column uses a window over the
-- grouped result — SUM(SUM(revenue)) OVER () is the grand total —
-- so no second query is needed for the denominator. The cleaning
-- underneath is the same chain as technique 7: dedup, price/date
-- parse, NULL rules, channel and category normalisation.
--
-- RETURNS: 4 rows, one per category, richest first.
-- EXPECTED: the four revenue_pkr values sum to PKR 346,800; shares
-- are 30.57 / 30.45 / 29.99 / 9.00 (rounded, so they sum to 100.01);
-- Kitchen leads on revenue; premium_lines counts only lines of
-- PKR 10,000 or more.

WITH catalogue AS (
    SELECT
        product_code,
        CASE UPPER(TRIM(category_raw))
            WHEN 'ELECTRONICS' THEN 'Electronics'
            WHEN 'ELEC.'        THEN 'Electronics'
            WHEN 'FURNITURE'   THEN 'Furniture'
            WHEN 'STATIONERY'  THEN 'Stationery'
            WHEN 'KITCHEN'     THEN 'Kitchen'
            ELSE 'UNMAPPED: ' || category_raw
        END AS category,
        CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                             'Rs.', ''), ',', ''), ' ', '')
             AS INTEGER) AS catalogue_price_pkr
    FROM raw_products
),
orders_clean AS (
    SELECT
        order_id,
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
        c.category,
        COALESCE(CAST(NULLIF(TRIM(li.quantity_text), '') AS INTEGER), 1)
            * COALESCE(
                CAST(REPLACE(REPLACE(REPLACE(
                         NULLIF(TRIM(li.unit_price_text), ''),
                         'Rs.', ''), ',', ''), ' ', '') AS INTEGER),
                c.catalogue_price_pkr) AS revenue_pkr
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY line_id ORDER BY updated_at DESC) AS rn
        FROM raw_order_items
    ) AS li
    JOIN catalogue AS c ON c.product_code = li.product_code
    WHERE rn = 1
)
SELECT
    l.category,
    COUNT(*) AS lines,
    COUNT(DISTINCT l.order_id) AS orders,
    SUM(l.revenue_pkr) AS revenue_pkr,
    SUM(CASE WHEN o.channel = 'Online' THEN l.revenue_pkr ELSE 0 END)
        AS online_pkr,
    SUM(CASE WHEN o.channel = 'In-Store' THEN l.revenue_pkr ELSE 0 END)
        AS in_store_pkr,
    SUM(CASE WHEN o.channel = 'Phone' THEN l.revenue_pkr ELSE 0 END)
        AS phone_pkr,
    ROUND(AVG(l.revenue_pkr), 2) AS avg_line_pkr,
    SUM(CASE WHEN l.revenue_pkr >= 10000 THEN 1 ELSE 0 END)
        AS premium_lines,
    ROUND(100.0 * SUM(l.revenue_pkr)
          / SUM(SUM(l.revenue_pkr)) OVER (), 2) AS share_pct
FROM lines_clean AS l
JOIN orders_clean AS o ON o.order_id = l.order_id
GROUP BY l.category
ORDER BY revenue_pkr DESC;
