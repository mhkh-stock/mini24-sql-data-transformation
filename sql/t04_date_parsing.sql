-- t04 — Date parsing: mixed date formats to ISO dates
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: order dates arrive in two formats — ISO "2026-01-08"
-- and DD/MM/YYYY "08/01/2026". As text they do not sort, strftime
-- cannot read the DD/MM/YYYY ones (it returns NULL), and "08/01"
-- is ambiguous: 8 January here, but 1 August to an American reader.
--
-- QUERY: a CASE spots the slash format (LIKE '%/%') and rebuilds
-- it as YYYY-MM-DD with SUBSTR — characters 7-10 are the year,
-- 4-5 the month, 1-2 the day. ISO values pass through untouched.
-- date() then proves every result is a real calendar date, and
-- strftime pulls the month for grouping.
--
-- RETURNS: 34 rows, one per raw order row (duplicates included —
-- dedup is technique 6). order_date_iso is ISO for every row.
-- EXPECTED: order 1 "08/01/2026" -> 2026-01-08; order 2 stays
-- 2026-02-14; 0 invalid dates; 17 slash dates and 17 ISO dates
-- (16 of each among the 32 live orders, plus one of each among the
-- 2 stale duplicates).

SELECT
    order_id,
    customer_code,
    order_date_text,
    CASE
        WHEN order_date_text LIKE '%/%' THEN
            SUBSTR(order_date_text, 7, 4) || '-'
            || SUBSTR(order_date_text, 4, 2) || '-'
            || SUBSTR(order_date_text, 1, 2)
        ELSE order_date_text
    END AS order_date_iso,
    strftime('%Y-%m',
        CASE
            WHEN order_date_text LIKE '%/%' THEN
                SUBSTR(order_date_text, 7, 4) || '-'
                || SUBSTR(order_date_text, 4, 2) || '-'
                || SUBSTR(order_date_text, 1, 2)
            ELSE order_date_text
        END) AS month,
    CASE
        WHEN date(CASE
            WHEN order_date_text LIKE '%/%' THEN
                SUBSTR(order_date_text, 7, 4) || '-'
                || SUBSTR(order_date_text, 4, 2) || '-'
                || SUBSTR(order_date_text, 1, 2)
            ELSE order_date_text
        END) IS NOT NULL THEN 'valid'
        ELSE 'INVALID'
    END AS date_check
FROM raw_orders
ORDER BY order_id, updated_at;
