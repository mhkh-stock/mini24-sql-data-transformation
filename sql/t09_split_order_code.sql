-- t09 — Splitting / extracting: SUBSTR + INSTR on a composite code
-- (SQL Data Transformation Pack, Mini #24 — SAMPLE data only)
--
-- PROBLEM: the order code packs two facts into one string —
-- "LAH-00001" is a city code plus an order number. As one string it
-- cannot be grouped by city, and the number cannot be sorted
-- numerically ("LAH-00010" sorts before "LAH-00002" as text).
--
-- QUERY: INSTR finds the hyphen; SUBSTR takes everything before it
-- as the city code and everything after it as the number, CAST to
-- INTEGER so it sorts and compares as a number. A CASE then maps
-- the code to the city name — "UNK" is the honest label for orders
-- whose customer had no city on file (Zainab Ali's and Omar
-- Farooq's orders), not a made-up city.
--
-- RETURNS: 32 rows, one per deduped order.
-- EXPECTED: order 1 -> LAH / 1 / Lahore; order 12 -> UNK / 12 /
-- Unknown; 5 orders carry UNK (12, 13, 23, 24, 28 — Zainab Ali's
-- and Omar Farooq's orders, whose customers have no city on file);
-- every order_no equals its order_id.

SELECT
    order_id,
    order_code,
    SUBSTR(order_code, 1, INSTR(order_code, '-') - 1) AS city_code,
    CAST(SUBSTR(order_code, INSTR(order_code, '-') + 1) AS INTEGER)
        AS order_no,
    CASE SUBSTR(order_code, 1, INSTR(order_code, '-') - 1)
        WHEN 'LAH' THEN 'Lahore'
        WHEN 'KHI' THEN 'Karachi'
        WHEN 'ISB' THEN 'Islamabad'
        WHEN 'RWP' THEN 'Rawalpindi'
        WHEN 'PEW' THEN 'Peshawar'
        WHEN 'MUX' THEN 'Multan'
        WHEN 'FSD' THEN 'Faisalabad'
        WHEN 'QUE' THEN 'Quetta'
        WHEN 'HYD' THEN 'Hyderabad'
        WHEN 'UNK' THEN 'Unknown'
        ELSE 'UNMAPPED'
    END AS city_name
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY order_id ORDER BY updated_at DESC) AS rn
    FROM raw_orders
)
WHERE rn = 1
ORDER BY order_id;
