-- Mini #24 — SQL Data Transformation Pack
-- SAMPLE / DEMO data only. Fictional shop Noor Electronics, fictional
-- people, fictional sales. Never claimed as real client or real
-- business data.
-- Bronze layer: the raw source exactly as it arrived — every column
-- TEXT, no constraints, no cleaning at load time. The mess stays in
-- the bronze tables so the SQL in sql/ can demonstrate fixing it.
-- Empty fields in the CSVs load as empty strings, NOT NULL: the
-- techniques turn blanks into NULL with NULLIF(TRIM(x), '').
-- SQLite 3.8.3+. Run: python3 src/build.py
-- (or: sqlite3 data/demo.db < data/schema.sql, then load the CSVs)

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS raw_order_items;
DROP TABLE IF EXISTS raw_orders;
DROP TABLE IF EXISTS raw_products;
DROP TABLE IF EXISTS raw_customers;

-- 15 rows, 12 unique customer_code values. updated_at decides which
-- row wins the dedup (technique 6): the latest row per code.
CREATE TABLE raw_customers (
    customer_code    TEXT NOT NULL,  -- CUST-001 .. CUST-012
    name             TEXT,           -- messy case / spaces
    city             TEXT,           -- messy case / spaces / blank
    signup_date_text TEXT,           -- ISO or DD/MM/YYYY
    email            TEXT,           -- blank when the source had none
    updated_at       TEXT NOT NULL   -- ISO date; latest row wins
);

-- 9 rows. category_raw holds 5 spellings of 4 categories;
-- price_text holds "Rs. 2,500" / "Rs.2500" / "2500" forms.
CREATE TABLE raw_products (
    product_code TEXT NOT NULL,  -- PRD-01 .. PRD-09
    name         TEXT NOT NULL,
    category_raw TEXT,           -- messy spelling
    price_text   TEXT            -- "Rs. 2,500" style text
);

-- 34 rows, 32 unique order_id values. order_date_text mixes ISO and
-- DD/MM/YYYY; channel_raw mixes 4 spellings of Online, 4 of
-- In-Store, 3 of Phone; order_code is the composite "LAH-00001".
CREATE TABLE raw_orders (
    order_id        INTEGER NOT NULL,
    customer_code   TEXT NOT NULL,  -- CUST-001 .. CUST-012
    order_date_text TEXT,           -- ISO or DD/MM/YYYY
    channel_raw     TEXT,           -- messy channel spelling
    order_code      TEXT,           -- e.g. "LAH-00001" (city + number)
    updated_at      TEXT NOT NULL   -- ISO date; latest row wins
);

-- 54 rows, 52 unique line_id values. quantity_text and
-- unit_price_text are text; line 5 has a blank quantity, line 8 a
-- blank price (the NULL-handling technique fixes both by rule).
CREATE TABLE raw_order_items (
    line_id         INTEGER NOT NULL,
    order_id        INTEGER NOT NULL,
    product_code    TEXT NOT NULL,  -- PRD-01 .. PRD-09
    quantity_text   TEXT,           -- "2" / " 3 " / blank
    unit_price_text TEXT,           -- "Rs. 2,500" style / blank
    updated_at      TEXT NOT NULL   -- ISO date; latest row wins
);
