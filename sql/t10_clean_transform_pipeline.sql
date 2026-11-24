-- t10 — Full clean-transform pipeline: bronze to silver in one query
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: techniques 1-9 each fix one kind of mess. A real
-- pipeline has to fix all of them, in the right order, in one pass
-- — and the result has to reconcile with the source, or the
-- cleaning itself is suspect.
--
-- QUERY: four CTEs, one per source table, each chaining the
-- techniques in dependency order:
--   customers: dedup by latest updated_at (t06) -> trim + collapse
--     double spaces (t03) -> proper-case the two-word name with
--     SUBSTR/INSTR -> blank city becomes 'Unknown' (t05) ->
--     slash dates to ISO (t04).
--   products: category recode (t01) + catalogue price parse (t02).
--   orders: dedup (t06) -> slash dates to ISO (t04) -> channel
--     normalise (t03) -> split the composite code (t09).
--   lines: dedup (t06) -> price/quantity parse (t02) -> NULLs by
--     rule, quantity 1 / catalogue price (t05) -> revenue.
-- The final SELECT joins the four clean CTEs into the silver mart:
-- one row per order line, every column clean, typed, and named.
-- In production this SELECT becomes CREATE TABLE clean_mart AS ...;
-- here it stays a SELECT so the file runs standalone like the rest.
--
-- RETURNS: 52 rows — one per deduped order line, Jan-Jun 2026.
-- EXPECTED: 52 rows; revenue sums to PKR 346,800, exactly the
-- clean base of Mini #1 / #3 / #15 / #22 / #23; 32 distinct
-- orders, 10 distinct customers, 0 NULLs in any column, 0
-- unmapped categories or channels, 5 orders from 'Unknown' city.

WITH customers_clean AS (
    SELECT
        customer_code,
        UPPER(SUBSTR(first_word, 1, 1)) || LOWER(SUBSTR(first_word, 2))
            || ' ' ||
        UPPER(SUBSTR(last_word, 1, 1)) || LOWER(SUBSTR(last_word, 2))
            AS customer_name,
        COALESCE(
            NULLIF(
                UPPER(SUBSTR(TRIM(city), 1, 1))
                || LOWER(SUBSTR(TRIM(city), 2)),
                ''),
            'Unknown') AS city,
        CASE
            WHEN signup_date_text LIKE '%/%' THEN
                SUBSTR(signup_date_text, 7, 4) || '-'
                || SUBSTR(signup_date_text, 4, 2) || '-'
                || SUBSTR(signup_date_text, 1, 2)
            ELSE signup_date_text
        END AS signup_date
    FROM (
        SELECT
            customer_code,
            SUBSTR(n, 1, INSTR(n, ' ') - 1) AS first_word,
            SUBSTR(n, INSTR(n, ' ') + 1) AS last_word,
            city,
            signup_date_text
        FROM (
            SELECT
                customer_code,
                TRIM(REPLACE(name, '  ', ' ')) AS n,
                city,
                signup_date_text,
                ROW_NUMBER() OVER (
                    PARTITION BY customer_code
                    ORDER BY updated_at DESC) AS rn
            FROM raw_customers
        )
        WHERE rn = 1
    )
),
products_clean AS (
    SELECT
        product_code,
        name AS product_name,
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
        customer_code,
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
        END AS channel,
        order_code,
        SUBSTR(order_code, 1, INSTR(order_code, '-') - 1) AS city_code
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
        li.line_id,
        li.order_id,
        li.product_code,
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
    JOIN products_clean AS c ON c.product_code = li.product_code
    WHERE rn = 1
)
SELECT
    o.order_id,
    o.order_date,
    strftime('%Y-%m', o.order_date) AS month,
    c.customer_code,
    c.customer_name,
    c.city,
    o.channel,
    o.order_code,
    o.city_code,
    p.product_code,
    p.product_name,
    p.category,
    l.quantity,
    l.unit_price_pkr,
    l.quantity * l.unit_price_pkr AS line_revenue_pkr
FROM lines_clean AS l
JOIN orders_clean AS o ON o.order_id = l.order_id
JOIN customers_clean AS c ON c.customer_code = o.customer_code
JOIN products_clean AS p ON p.product_code = l.product_code
ORDER BY o.order_id, l.line_id;
