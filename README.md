# Mini #24 — SQL Data Transformation Pack

**Status:** built, verified locally — publish pending

**SAMPLE / DEMO data only.** Fictional store, fictional sales,
fictional numbers. Never claimed as real client work.

**Why this pack:** Data Transformation re-entered the London
contract top 30 at 11.3% in the 24 Nov 2026 market watch, after
two days out — and Data Modelling is holding 19.5–22%. Employers
are not asking for SELECT * any more; they are asking whether you
can take the messy extract a real system sends and turn it into a
table a dashboard can trust. This pack is that skill, ten
techniques deep, on one deliberately messy dataset: mixed-case
names, "Rs. 1,250" style price text, two date formats, blank
fields, duplicate rows, nine spellings of four categories, eleven
spellings of three channels. Every technique ships as its own
`.sql` file with the problem stated in its header comment, plus
the CSV of its exact expected output — so anyone can run the query
and check their answer against the file. The tenth technique
chains the other nine into a full bronze-to-silver pipeline, and
the clean mart reconciles to the rupee against the source.

## Business question

"Can I trust this extract — and what does it take to make it
trustworthy?"

## What is inside

| File | What it does |
|---|---|
| `outputs/findings.md` | The teaching write-up: headline numbers + what each technique proves, one common mistake per technique |
| `outputs/summary.json` | Every verified headline number, machine-readable |
| `outputs/test_results.json` | The automated check run: how many checks passed |
| `outputs/technique_01_case_category_price_bands.csv` | Technique 1 output — 9 products, recoded categories + price bands |
| `outputs/technique_02_cast_text_to_numbers.csv` | Technique 2 output — 54 lines, text prices and quantities as numbers |
| `outputs/technique_03_string_cleaning.csv` | Technique 3 output — 15 customer rows, cleaned names, cities, emails |
| `outputs/technique_04_date_parsing.csv` | Technique 4 output — 34 order rows, all dates ISO |
| `outputs/technique_05_null_handling.csv` | Technique 5 output — 54 lines, NULLs filled by stated rule |
| `outputs/technique_06_dedup_row_number.csv` | Technique 6 output — 12 customers, latest row per code |
| `outputs/technique_07_pivot_sales_by_channel.csv` | Technique 7 output — 6 months × 3 channels pivot |
| `outputs/technique_08_conditional_aggregation_kpis.csv` | Technique 8 output — 4 categories, KPIs in one pass |
| `outputs/technique_09_split_order_code.csv` | Technique 9 output — 32 orders, code split into city + number |
| `outputs/technique_10_clean_transform_pipeline.csv` | Technique 10 output — the 52-row clean mart |
| `sql/t01_case_category_price_bands.sql` | Technique 1 — CASE recode + price bands |
| `sql/t02_cast_text_to_numbers.sql` | Technique 2 — CAST + type conversion |
| `sql/t03_string_cleaning.sql` | Technique 3 — TRIM / UPPER / REPLACE / SUBSTR |
| `sql/t04_date_parsing.sql` | Technique 4 — mixed date formats to ISO |
| `sql/t05_null_handling.sql` | Technique 5 — COALESCE / NULLIF |
| `sql/t06_dedup_row_number.sql` | Technique 6 — dedup with ROW_NUMBER() |
| `sql/t07_pivot_sales_by_channel.sql` | Technique 7 — pivoting with CASE |
| `sql/t08_conditional_aggregation_kpis.sql` | Technique 8 — conditional aggregation |
| `sql/t09_split_order_code.sql` | Technique 9 — SUBSTR + INSTR splitting |
| `sql/t10_clean_transform_pipeline.sql` | Technique 10 — bronze-to-silver pipeline |
| `data/schema.sql` | Bronze schema — four raw tables, all TEXT |
| `data/raw/customers_raw_SAMPLE.csv` | 15 messy customer rows (12 unique codes) |
| `data/raw/products_raw_SAMPLE.csv` | 9 products, messy categories + price text |
| `data/raw/orders_raw_SAMPLE.csv` | 34 messy order rows (32 unique ids) |
| `data/raw/order_items_raw_SAMPLE.csv` | 54 messy line rows (52 unique ids) |
| `data/demo.db` | SQLite database, rebuilt by `src/build.py` (not uploaded to GitHub) |
| `data/README.md` | Data dictionary + the full mess inventory |
| `src/generate_data.py` | Regenerates all SAMPLE CSVs (deterministic, no randomness) |
| `src/build.py` | Builds the DB, runs all 10 queries, writes outputs + summary.json |
| `src/checks.py` | Checks as code — every number re-derived from the raw CSVs |
| `src/run_tests.py` | Test runner — runs checks.py, prints PASS/FAIL |
| `requirements.txt` | Standard library only — no dependencies |

## Key numbers (real numbers, recomputed from the raw CSVs)

| KPI | Value |
|---|---|
| Raw bronze rows | 15 customers · 9 products · 34 orders · 54 lines |
| Clean silver mart | 12 customers · 32 orders · 52 lines |
| Clean revenue | PKR 346,800 |
| Dedup removed | 3 customer rows · 2 order rows · 2 line rows |
| NULLs fixed by rule | 2 lines, worth PKR 32,500 (9.37% of revenue) |
| Monthly revenue | Jan 37,100 · Feb 50,000 · Mar 30,500 · Apr 62,100 · May 72,900 · Jun 94,200 |
| Revenue by channel | Phone PKR 117,000 (33.74%) · Online PKR 116,600 (33.62%) · In-Store PKR 113,200 (32.64%) |
| Orders by channel | Online 11 · In-Store 10 · Phone 11 |
| Revenue by category | Kitchen PKR 106,000 · Furniture PKR 105,600 · Electronics PKR 104,000 · Stationery PKR 31,200 |
| Category shares | Kitchen 30.57% · Furniture 30.45% · Electronics 29.99% · Stationery 9.00% |
| Price bands | Budget 2 · Mid-range 5 · Premium 2 |
| Dearest / cheapest product | Office Chair PKR 18,000 / Notebook Set PKR 1,200 |
| NULL price fallback | Dinner Set catalogue PKR 14,500 (line 8) |
| Premium lines (PKR 10,000+) | 8 — 4 Kitchen (Dinner Sets) + 4 Furniture (Office Chairs) |
| Highest average line | Furniture PKR 10,560.00 |
| Date formats in source | 17 DD/MM/YYYY · 17 ISO · 0 invalid after parsing |
| Unknown-city orders | 5 (Zainab Ali's and Omar Farooq's — no city on file) |
| Checks | see `python3 src/checks.py` |

## The 10 techniques

| # | Technique | SQL | What it answers |
|---|---|---|---|
| 1 | CASE recode + price bands | `sql/t01_*.sql` | Five spellings of one category — which is it really, and is it cheap or premium? |
| 2 | CAST + type conversion | `sql/t02_*.sql` | "Rs. 8,500" is text — what is it as a number I can sum? |
| 3 | String cleaning | `sql/t03_*.sql` | "  ayesha khan" vs "FATIMA NOOR" — who is this customer, really? |
| 4 | Date parsing | `sql/t04_*.sql` | "08/01/2026" — 8 January or 1 August, and can it group by month? |
| 5 | NULL handling | `sql/t05_*.sql` | A line with no quantity and a line with no price — drop them, or fix them by rule? |
| 6 | Dedup with ROW_NUMBER() | `sql/t06_*.sql` | The source sent the same customer twice — which row is the truth? |
| 7 | Pivoting with CASE | `sql/t07_*.sql` | One row per month, one column per channel — who sold what, where? |
| 8 | Conditional aggregation | `sql/t08_*.sql` | Four KPIs per category — can one query answer them all? |
| 9 | Splitting / extracting | `sql/t09_*.sql` | "LAH-00001" packs city + number — what is each half? |
| 10 | Full clean-transform pipeline | `sql/t10_*.sql` | All of the above, chained, bronze to silver — does it reconcile? |

## What the pack teaches

1. **A blank is not a zero.** `CAST('' AS INTEGER)` returns 0 in
   SQLite, so a missing price parsed without NULLIF becomes a free
   item. Turn blanks into NULL first, then decide by rule what
   NULL means — and write the rule down.
2. **Cleaning that does not reconcile is guessing.** The mart
   proves itself against the source: same 32 orders, same 52
   lines, same PKR 346,800 as the clean base Mini #1 / #3 / #15 /
   #22 / #23 verified. If a transform changes the total, the
   transform is wrong until proven otherwise.
3. **Keep the raw beside the clean.** Every technique shows the
   raw column next to the cleaned one. A cleaning step you cannot
   audit is a cleaning step you cannot trust — and the bronze
   tables are never overwritten, so any step can be re-run.
4. **Order matters: dedup before cleaning, parse before
   aggregating.** Cleaning a stale duplicate is wasted work, and
   aggregating text prices is a wrong answer. Technique 10 chains
   the steps in dependency order for exactly this reason.
5. **Unmapped is a valid answer; silently dropped is not.** Every
   CASE in the pack has an ELSE that labels what it could not map.
   The checks assert 0 unmapped values only because the planted
   mess is fully mapped — in production the ELSE branch is where
   the reject table starts.

## Verified numbers

| KPI | Value |
|---|---|
| Clean revenue | PKR 346,800 |
| Raw → clean | 15/34/54 rows → 12/32/52 rows |
| NULLs fixed | 2 lines, PKR 32,500 |
| Top channel / category | Phone PKR 117,000 / Kitchen PKR 106,000 |
| Premium lines | 8 |
| Unknown-city orders | 5 |
| Checks | see `python3 src/checks.py` |

Verification: `python3 src/checks.py` — every headline number is
recomputed from the raw CSVs with the standard library only (no
pandas) and compared against every output CSV, summary.json,
findings.md and this README; every query is re-run against a
freshly rebuilt database and its output byte-compared with the
shipped CSVs; and the generator re-run is byte-compared for
determinism (see `src/checks.py`).

## How to run it

1. No dependencies to install — Python 3 standard library only
   (`sqlite3`, `csv`, `json`).
2. Read `outputs/findings.md` — that is the deliverable.
3. To regenerate the sample data: `python3 src/generate_data.py`.
4. To rebuild the database and re-run all 10 techniques:
   `python3 src/build.py`.
5. To check it: `python3 src/checks.py`.
6. Or run the test suite: `python3 src/run_tests.py`.
7. To run a single technique by hand:
   `sqlite3 data/demo.db < sql/t07_pivot_sales_by_channel.sql`.
8. To practise on your own data: replace the raw CSVs (same
   columns) and re-run steps 4–6 only — do NOT re-run step 3, it
   regenerates the sample data and would overwrite your files.

## Two traps this pack teaches

- **A blank is not a zero.** `CAST('' AS INTEGER)` returns 0 in
  SQLite. A missing price parsed without NULLIF becomes a free
  item; a missing quantity becomes a line that never happened.
  Turn blanks into NULL first, then decide by rule — and write
  the rule down.
- **Cleaning that does not reconcile is guessing.** The mart
  proves itself against the source: same 32 orders, same 52
  lines, same PKR 346,800. If a transform changes the total, the
  transform is wrong until proven otherwise — never the data.

## Limits

- **SAMPLE data only.** The store, the sales and the "findings"
  are invented to teach the techniques.
- **The mess is planted, not found.** Real source mess is less
  tidy — more formats, more spellings, values that parse to
  nothing at all. This pack has no reject table for unparseable
  rows; a production pipeline needs one, and the checks here
  assert 0 unmapped values only because the planted mess is fully
  mapped.
- **Proper-case in pure SQL is brittle.** The pipeline
  proper-cases two-word names and one-word cities with
  SUBSTR/INSTR. A three-word name or a two-word city ("Dera Ghazi
  Khan") would break the pattern — in production that step belongs
  in Python or in a mapping table, not in a SUBSTR expression.
- **One shop, six months, 52 lines.** The patterns scale — the
  row counts do not.

## Published

Not published yet — built and verified locally 24 Nov 2026.
