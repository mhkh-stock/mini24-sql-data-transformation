-- t05 — NULL handling: COALESCE / NULLIF with a stated rule
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: two order lines are missing a value — line 5 has no
-- quantity, line 8 has no price. Dropping the lines would lose
-- PKR 32,500 of revenue; treating the blanks as 0 would book two
-- free items. Either way the mart would be wrong, and silently so.
--
-- QUERY: COALESCE fills each gap by a stated rule, written in the
-- open so a reviewer can argue with it:
--   * missing quantity -> 1 (the line is one item; the quantity
--     field was left blank, the item was still sold once)
--   * missing price -> the product's current catalogue price
--     (the till price on the day is unknown; the catalogue price
--     is the documented fallback, and the line is flagged)
-- NULLIF(TRIM(x), '') is what turns the source's blank fields into
-- real NULLs first — without it, CAST('' AS INTEGER) returns 0.
-- null_flag marks every line a rule touched.
--
-- RETURNS: 54 rows — every raw order line (duplicates included;
-- dedup is technique 6). quantity_clean and unit_price_clean are
-- never NULL; line_revenue_pkr is computed on the cleaned values.
-- EXPECTED: line 5 quantity NULL -> 1, revenue PKR 18,000; line 8
-- price NULL -> catalogue PKR 14,500, revenue PKR 14,500; exactly
-- 2 rows flagged "fixed NULL".

WITH catalogue AS (
    SELECT
        product_code,
        CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                             'Rs.', ''), ',', ''), ' ', '')
             AS INTEGER) AS catalogue_price_pkr
    FROM raw_products
),
parsed AS (
    SELECT
        line_id,
        order_id,
        product_code,
        quantity_text,
        CAST(NULLIF(TRIM(quantity_text), '') AS INTEGER) AS quantity_int,
        unit_price_text,
        CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(unit_price_text), ''),
                             'Rs.', ''), ',', ''), ' ', '')
             AS INTEGER) AS unit_price_int,
        updated_at
    FROM raw_order_items
)
SELECT
    p.line_id,
    p.order_id,
    p.product_code,
    p.quantity_text,
    p.quantity_int,
    COALESCE(p.quantity_int, 1) AS quantity_clean,
    p.unit_price_text,
    p.unit_price_int,
    COALESCE(p.unit_price_int, c.catalogue_price_pkr)
        AS unit_price_clean,
    COALESCE(p.quantity_int, 1)
        * COALESCE(p.unit_price_int, c.catalogue_price_pkr)
        AS line_revenue_pkr,
    CASE
        WHEN p.quantity_int IS NULL OR p.unit_price_int IS NULL
        THEN 'fixed NULL'
        ELSE 'ok'
    END AS null_flag
FROM parsed AS p
JOIN catalogue AS c ON c.product_code = p.product_code
ORDER BY p.line_id, p.updated_at;
