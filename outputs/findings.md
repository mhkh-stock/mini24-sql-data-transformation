# Mini #24 — findings: what each transformation proves

**SAMPLE / DEMO data only.** Fictional store "Noor Electronics",
fictional sales, Jan–Jun 2026. The transformation techniques are
real; the business is not. Every number below is recomputed from
the raw CSVs by `src/checks.py` and matches `outputs/summary.json`
and the README exactly.

## Headline numbers

- Raw bronze: 15 customer rows, 9 products, 34 order rows,
  54 line rows.
- Clean silver mart: 12 customers, 32 orders, 52 lines,
  **PKR 346,800** — exactly the clean base of Mini #1 / #3 / #15 /
  #22 / #23. The mess was formatting only, and the mart proves it.
- Dedup removed 7 stale rows (3 customers, 2 orders, 2 lines).
- NULL rules fixed 2 lines (line 5 quantity, line 8 price),
  worth PKR 32,500 — revenue that dropping the lines would lose.
- Monthly revenue: Jan 37,100 · Feb 50,000 · Mar 30,500 ·
  Apr 62,100 · May 72,900 · Jun 94,200.
- Channels are nearly level: Phone PKR 117,000 (33.74%), Online
  PKR 116,600 (33.62%), In-Store PKR 113,200 (32.64%).
- Categories are nearly level too: Kitchen PKR 106,000 (30.57%),
  Furniture PKR 105,600 (30.45%), Electronics PKR 104,000
  (29.99%), Stationery PKR 31,200 (9.00%).

## Technique by technique

### 1 — CASE recodes categories and bands prices
Nine raw spellings collapse to four canonical categories, and the
catalogue bands as 2 Budget, 5 Mid-range, 2 Premium. The one that
matters is "Elec." → Electronics: an abbreviation is a spelling,
not a category, and a CASE that only handles the spellings you
have seen will misfile the next one — hence the ELSE branch that
labels anything unmapped instead of dropping it. The dearest
product is the Office Chair at PKR 18,000 (Premium); the cheapest
is the Notebook Set at PKR 1,200 (Budget).

### 2 — CAST turns text prices into numbers
"Rs. 8,500" → 8500, "Rs.2500" → 2500, " 3 " → 3. The technique is
two lines, but the trap is in the blank: `CAST('' AS INTEGER)`
returns 0 in SQLite, so a missing price would silently become a
free item. The file wraps every value in `NULLIF(TRIM(x), '')`
first, so blanks stay NULL and the NULL-handling technique can
deal with them by rule. Line 1 proves the arithmetic: 2 × 2500 =
PKR 5,000.

### 3 — String cleaning makes grouping possible
"  ayesha khan", "FATIMA NOOR" and "Ayesha  Khan" are three rows
about two people until TRIM, REPLACE (double space) and UPPER run.
The file keeps the raw column beside the cleaned one — a cleaning
step you cannot audit is a cleaning step you cannot trust. It also
splits the name with SUBSTR + INSTR (first "ayesha", last "khan")
and shows NULLIF on the city: blank city is NULL, not an empty
string pretending to be a place. Email is LOWERed, not UPPERed —
case matters for display, not for a mailbox.

### 4 — Date parsing ends the format argument
17 dates arrive as DD/MM/YYYY, 17 as ISO, and the CASE rebuilds
the slash ones as YYYY-MM-DD with SUBSTR. Order 1 "08/01/2026"
becomes 2026-01-08 — 8 January, not 1 August. Every result passes
`date()`, so 0 of 34 are invalid, and the month column groups
cleanly. The rule is written once, in one CASE, and reused by the
pipeline — two different date parsers in one codebase is how a
report ends up counting January twice.

### 5 — NULL handling, with the rule in writing
Line 5 has no quantity, line 8 has no price, and the file states
its rules instead of hiding them: missing quantity counts as 1
(one item was still sold), missing price falls back to the
catalogue price (PKR 14,500 for the Dinner Set). The two lines
are worth PKR 32,500 — dropping them would understate revenue by
9.37%, and zero-filling them would book two free items. Both lines
carry the flag "fixed NULL" so a reviewer can find them. A rule
that is not written down is a guess the next analyst cannot check.

### 6 — Dedup keeps the latest, not the first
ROW_NUMBER() over (PARTITION BY customer_code ORDER BY
updated_at DESC), keep rn = 1: 15 rows become 12 customers.
CUST-001 keeps "Ayesha Khan" (2026-03-10), not the "  ayesha khan"
row of 2026-01-05; CUST-003 keeps "Fatima Noor" of Islamabad
(2026-04-02), not the blank-city row of 2026-02-01. DISTINCT
cannot do this job — the duplicate rows differ, so they are not
duplicates to DISTINCT. The same pattern, with a different key,
removes 2 stale orders and 2 stale lines.

### 7 — Pivoting turns rows into a readable month table
One row per month, one column per channel: January reads
Online 19,300 / In-Store 11,800 / Phone 6,000 / total 37,100.
Every month sells on all three channels, and every row total is
the monthly revenue while the column totals are the channel
totals — the pivot reconciles both ways to PKR 346,800. The
honest zero matters: COALESCE(..., 0) prints 0 where a channel
did not sell, instead of a blank that looks like missing data.
SQLite has no PIVOT keyword; SUM(CASE...) is the portable way.

### 8 — Conditional aggregation answers four questions in one pass
Per category: lines, orders, revenue, revenue by channel,
average line value, premium lines (PKR 10,000+), share of total.
Kitchen leads revenue at PKR 106,000, but Furniture has the
highest average line (PKR 10,560.00) and shares the premium lead
with Kitchen at 4 lines each — all 8 premium lines are Office
Chairs and Dinner Sets. Electronics, with the most lines (19),
has zero premium lines: it sells volume, not ticket size.
Stationery is 9.00% of revenue on 9 lines. One GROUP BY, one
scan; the share column gets its denominator from a window over
the grouped result, not a second query.

### 9 — Splitting the composite code
"LAH-00001" splits at the hyphen into city LAH and number 1, and
the number is CAST to INTEGER so it sorts numerically. Five
orders carry UNK (12, 13, 23, 24, 28) — Zainab Ali's and Omar
Farooq's orders, whose customers have no city on file. "Unknown"
is the honest label: inventing a city for those orders would make
the city report wrong in a way nobody could trace back.

### 10 — The full pipeline: bronze to silver in one query
Four CTEs — one per source table — chain techniques 1–9 in
dependency order (dedup before cleaning, parse before
aggregating, NULL rules before revenue), and the final SELECT
joins them into a 52-row mart with 15 clean columns. It
reconciles exactly: 52 lines, 32 orders, 10 buying customers,
8 products sold, PKR 346,800, 0 NULLs in any column, 0 unmapped
categories or channels, 5 orders from 'Unknown' city. In
production this SELECT becomes CREATE TABLE clean_mart AS ...;
the pack keeps it a SELECT so the file runs standalone like the
other nine.

## Two traps this pack teaches

- **A blank is not a zero.** `CAST('' AS INTEGER)` returns 0 in
  SQLite, so a missing price parsed without NULLIF becomes a free
  item and a missing quantity becomes a line that never happened.
  Turn blanks into NULL first, then decide by rule what NULL
  means — and write the rule down.
- **Cleaning that does not reconcile is guessing.** The mart
  proves itself against the source: same 32 orders, same 52
  lines, same PKR 346,800 as the clean base the other minis
  verified. If a transform changes the total, the transform is
  wrong until proven otherwise — never the data.

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
