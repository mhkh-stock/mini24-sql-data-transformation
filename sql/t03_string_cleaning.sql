-- t03 — String cleaning: TRIM / UPPER / REPLACE / SUBSTR
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: names arrive as "  ayesha khan", "FATIMA NOOR",
-- "Ayesha  Khan" (double space) and cities as "lahore",
-- "  rawalpindi " — so "Ayesha Khan" and "ayesha khan" group as two
-- different customers and "Lahore" and "lahore" as two cities.
--
-- QUERY: TRIM takes the edges off, REPLACE collapses the double
-- space inside, UPPER gives one canonical case for grouping, and
-- SUBSTR + INSTR split the cleaned name into first and last name.
-- Email gets LOWER instead — "Ayesha@Example.pk" and
-- "ayesha@example.pk" are the same mailbox. Nothing is overwritten:
-- the raw column stays beside the cleaned one so the change is
-- auditable.
--
-- RETURNS: 15 rows, one per raw customer row (duplicates included —
-- dedup is technique 6). name_upper is the grouping key; first_name
-- and last_name are the split.
-- EXPECTED: "  ayesha khan" -> trimmed "ayesha khan", upper
-- "AYESHA KHAN", first "ayesha", last "khan"; "  rawalpindi " ->
-- city_upper "RAWALPINDI"; 15 rows, 12 distinct customer codes.

WITH cleaned AS (
    SELECT
        customer_code,
        name AS name_raw,
        TRIM(REPLACE(name, '  ', ' ')) AS name_trimmed,
        city AS city_raw,
        TRIM(city) AS city_trimmed,
        LOWER(TRIM(email)) AS email_clean,
        updated_at
    FROM raw_customers
)
SELECT
    customer_code,
    name_raw,
    name_trimmed,
    UPPER(name_trimmed) AS name_upper,
    SUBSTR(name_trimmed, 1, INSTR(name_trimmed, ' ') - 1) AS first_name,
    SUBSTR(name_trimmed, INSTR(name_trimmed, ' ') + 1) AS last_name,
    city_raw,
    city_trimmed,
    UPPER(city_trimmed) AS city_upper,
    NULLIF(city_trimmed, '') AS city_nullif,
    email_clean,
    updated_at
FROM cleaned
ORDER BY customer_code, updated_at;
