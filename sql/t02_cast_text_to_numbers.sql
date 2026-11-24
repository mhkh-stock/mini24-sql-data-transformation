-- t02 — CAST + type conversion: text prices and quantities to numbers
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: quantity and price arrive as text — "Rs. 2,500",
-- "Rs.2500", "2500", " 3 " with spaces, and blanks where the source
-- had no value. Text cannot be multiplied, summed, or compared as a
-- number ("Rs. 8,500" > "Rs. 2,500" is false as text).
--
-- QUERY: strip the currency marker, the thousands commas and the
-- spaces, then CAST to INTEGER. Blanks become NULL first, via
-- NULLIF(TRIM(x), '') — without that step CAST('' AS INTEGER) would
-- silently return 0 and a missing price would look like a free item.
-- The CAST is the conversion; the REPLACE chain is just removing
-- formatting the number never needed.
--
-- RETURNS: 54 rows — every raw order line, including the 2 stale
-- duplicates (dedup is technique 6). quantity_int and unit_price_pkr
-- are NULL exactly where the source was blank (line 5 quantity,
-- line 8 price); line_revenue_pkr is NULL on those two lines until
-- technique 5 fills them by rule.
-- EXPECTED: "Rs. 8,500" -> 8500; "Rs.2500" -> 2500; " 3 " -> 3;
-- line 1 revenue = 2 x 2500 = 5000; exactly 2 NULL prices/quantities.

SELECT
    line_id,
    order_id,
    product_code,
    quantity_text,
    CAST(NULLIF(TRIM(quantity_text), '') AS INTEGER) AS quantity_int,
    unit_price_text,
    CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(unit_price_text), ''),
                         'Rs.', ''), ',', ''), ' ', '')
         AS INTEGER) AS unit_price_pkr,
    CAST(NULLIF(TRIM(quantity_text), '') AS INTEGER)
    * CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(unit_price_text), ''),
                           'Rs.', ''), ',', ''), ' ', '')
           AS INTEGER) AS line_revenue_pkr
FROM raw_order_items
ORDER BY line_id, updated_at;
