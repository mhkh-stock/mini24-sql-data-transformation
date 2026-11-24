# Mini #24 — data dictionary (SAMPLE / DEMO only)

Fictional store "Noor Electronics" — the same made-up Pakistani
electronics store as Mini #1 / #3 / #15 / #22 / #23, Jan–Jun 2026.
The store, the sales and every number are invented for teaching —
the transformation techniques are real, the business is not.
Regenerate exactly with `python3 src/generate_data.py`
(deterministic, no randomness). Build the database and run all 10
techniques with `python3 src/build.py`.

## The bronze layer — deliberately messy

Unlike Mini #23, which charts the **clean** base, this pack starts
from the mess: the same 32 orders / 52 lines / PKR 346,800, but as
the source system actually sends it. The mess is formatting only —
every value parses back to the clean base, so the clean mart
(technique 10) must reconcile exactly to PKR 346,800. If it does
not, the cleaning is wrong, not the data.

What is messy, and where it is fixed:

| Mess | Where | Fixed by |
|---|---|---|
| 9 raw spellings of 4 categories ("electronics", "Electronics ", "ELECTRONICS", "Elec.", "Furniture", "furniture", "stationery", "Kitchen", "kitchen ") | `products_raw` | t01 CASE recode |
| Price as text: "Rs. 2,500" / "Rs.2500" / "2500" / trailing spaces | `products_raw`, `order_items_raw` | t02 CAST |
| Names "  ayesha khan" / "FATIMA NOOR" / "Ayesha  Khan"; cities "lahore" / "  rawalpindi " | `customers_raw` | t03 string cleaning |
| Dates in ISO and DD/MM/YYYY side by side | `customers_raw`, `orders_raw` | t04 date parsing |
| Blank quantity (line 5), blank price (line 8), blank cities and emails | `order_items_raw`, `customers_raw` | t05 COALESCE / NULLIF |
| Duplicate rows: 15 customer rows for 12 customers, 34 order rows for 32 orders, 54 line rows for 52 lines | all raw tables | t06 ROW_NUMBER dedup |
| 11 spellings of 3 channels ("online", "ONLINE", "In Store", "instore" ...) | `orders_raw` | t07 pivot (normalised inline) |
| Composite code "LAH-00001" packing city + number | `orders_raw` | t09 SUBSTR + INSTR |

Empty fields in the CSVs load into the database as empty strings,
not NULL — that is how the source sends them. The SQL turns blanks
into NULL with `NULLIF(TRIM(x), '')` before any CAST, because
`CAST('' AS INTEGER)` silently returns 0 and a missing price would
look like a free item.

## data/raw/customers_raw_SAMPLE.csv (15 rows)

| Column | Meaning |
|---|---|
| `customer_code` | Customer key, CUST-001 – CUST-012 (3 codes appear twice) |
| `name` | Customer name, messy case and spacing |
| `city` | City, messy case and spacing; blank when the source had none |
| `signup_date_text` | Signup date, ISO or DD/MM/YYYY |
| `email` | Email, blank when the source had none |
| `updated_at` | Row version date — the latest row per code wins the dedup |

12 unique customers. The latest rows: Ayesha Khan (Lahore),
Bilal Ahmed (Karachi), Fatima Noor (Islamabad), Hassan Raza
(Rawalpindi), Zainab Ali (no city), Usman Tariq (Peshawar), Maryam
Siddiqui (Lahore), Ali Nawaz (Multan), Sara Malik (Faisalabad),
Omar Farooq (no city), Hina Shah (Quetta), Danish Iqbal
(Hyderabad). Only 10 of the 12 ever ordered (Hina Shah and Danish
Iqbal never bought).

## data/raw/products_raw_SAMPLE.csv (9 rows)

| Column | Meaning |
|---|---|
| `product_code` | Product key, PRD-01 – PRD-09 |
| `name` | Product name |
| `category_raw` | Category in one of 5 raw spellings |
| `price_text` | Catalogue price as "Rs. 2,500" style text |

Clean categories: Electronics (Mouse, Keyboard, Laptop Stand,
Bluetooth Speaker), Furniture (Office Chair, Desk Lamp),
Stationery (Notebook Set), Kitchen (Mug Set, Dinner Set).
Bluetooth Speaker (PRD-09, PKR 6,500) never sold.

## data/raw/orders_raw_SAMPLE.csv (34 rows)

| Column | Meaning |
|---|---|
| `order_id` | Order number, 1–32 (orders 7 and 19 appear twice — stale copies) |
| `customer_code` | Buyer — CUST-001 – CUST-010 |
| `order_date_text` | Order date, ISO or DD/MM/YYYY (16 of each among the 32 live orders) |
| `channel_raw` | Sales channel in one of 11 raw spellings |
| `order_code` | Composite code: city prefix + zero-padded number, e.g. "LAH-00001" |
| `updated_at` | Row version date — the latest row per order wins the dedup |

Channels once cleaned: Online 11 orders, In-Store 10, Phone 11.
City prefixes: LAH Lahore, KHI Karachi, ISB Islamabad, RWP
Rawalpindi, PEW Peshawar, MUX Multan, FSD Faisalabad, QUE Quetta,
HYD Hyderabad, UNK unknown (customers with no city on file).

## data/raw/order_items_raw_SAMPLE.csv (54 rows)

| Column | Meaning |
|---|---|
| `line_id` | Order-line number, 1–52 (lines 10 and 25 appear twice — stale copies) |
| `order_id` | Order the line belongs to |
| `product_code` | Product — PRD-01 – PRD-08 (PRD-09 never sold) |
| `quantity_text` | Units on the line as text; blank on line 5 |
| `unit_price_text` | Price charged as "Rs. 2,500" style text; blank on line 8 |
| `updated_at` | Row version date — the latest row per line wins the dedup |

Line revenue is always `quantity × unit_price_pkr` after cleaning.
The 52 clean lines total PKR 346,800; 81 units in total. The two
NULL rules (technique 5): blank quantity counts as 1 (line 5 still
sells one Office Chair, PKR 18,000); blank price falls back to the
catalogue price (line 8 still sells one Dinner Set at PKR 14,500).

## data/schema.sql

Bronze schema: four raw tables, every column TEXT, no constraints —
the load does not clean anything, so the mess stays visible for
the SQL to fix. `data/demo.db` is built from it by `src/build.py`
and is rebuildable at any time; it is not uploaded to GitHub.

## Totals (verified)

- Raw: 15 customer rows, 9 products, 34 order rows, 54 line rows.
- Clean: 12 customers, 32 orders, 52 lines, total revenue
  PKR 346,800 — the same clean base as Mini #1 / #3 / #15 / #22 /
  #23, reconciled exactly by the technique-10 mart.
- Monthly revenue: Jan 37,100 · Feb 50,000 · Mar 30,500 ·
  Apr 62,100 · May 72,900 · Jun 94,200.
- Revenue by category: Electronics PKR 104,000 · Furniture
  PKR 105,600 · Kitchen PKR 106,000 · Stationery PKR 31,200.
- Revenue by channel: Online PKR 116,600 · In-Store PKR 113,200 ·
  Phone PKR 117,000.
- Dedup removes 3 customer rows, 2 order rows, 2 line rows.
- NULL rules fix 2 lines (line 5 quantity, line 8 price).

## Known quirks

- **SAMPLE data only.** The store, the sales and the "findings"
  are invented to teach the techniques.
- **The mess is planted, not found.** Real source mess is less
  tidy — more formats, more spellings, values that parse to
  nothing at all. The pack teaches the patterns; a real pipeline
  also needs a reject table for the rows no rule can save, and
  this pack says so in its findings instead of pretending every
  row is fixable.
- **The channel per order is hand-assigned** (see
  `src/generate_data.py`) so every month sells on all three
  channels; a modulo rule would have tied channel to order number
  and made January 100% Online.
