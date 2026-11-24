-- t01 — CASE: recode categories and build price bands
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: the source catalogue spells Electronics four ways
-- ("electronics", "Electronics ", "ELECTRONICS", "Elec.") and the
-- price is text ("Rs. 2,500"), so neither the category nor a price
-- band can be grouped on as-is.
--
-- QUERY: one CASE maps every raw spelling to the canonical category
-- (the ELSE branch keeps anything unmapped visible instead of
-- silently dropping it); a second CASE bands the parsed price into
-- Budget / Mid-range / Premium. The price parsing itself (strip
-- "Rs.", commas, spaces, then CAST) is technique 2 — it is inlined
-- here only so this file runs on its own.
--
-- RETURNS: 9 rows, one per product — raw category, canonical
-- category, parsed price in PKR, price band.
-- EXPECTED: "Elec." (PRD-09) recodes to Electronics; 2 Budget,
-- 5 Mid-range, 2 Premium; Office Chair is the dearest at PKR 18,000.

SELECT
    product_code,
    name,
    category_raw,
    CASE UPPER(TRIM(category_raw))
        WHEN 'ELECTRONICS' THEN 'Electronics'
        WHEN 'ELEC.'        THEN 'Electronics'
        WHEN 'FURNITURE'   THEN 'Furniture'
        WHEN 'STATIONERY'  THEN 'Stationery'
        WHEN 'KITCHEN'     THEN 'Kitchen'
        ELSE 'UNMAPPED: ' || category_raw
    END AS category_clean,
    CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                         'Rs.', ''), ',', ''), ' ', '')
         AS INTEGER) AS price_pkr,
    CASE
        WHEN CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                                  'Rs.', ''), ',', ''), ' ', '')
                  AS INTEGER) < 3000  THEN 'Budget (< PKR 3,000)'
        WHEN CAST(REPLACE(REPLACE(REPLACE(NULLIF(TRIM(price_text), ''),
                                  'Rs.', ''), ',', ''), ' ', '')
                  AS INTEGER) < 10000 THEN 'Mid-range (PKR 3,000-9,999)'
        ELSE 'Premium (PKR 10,000+)'
    END AS price_band
FROM raw_products
ORDER BY product_code;
