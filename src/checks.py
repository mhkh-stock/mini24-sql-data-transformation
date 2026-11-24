"""Independent checks for Mini #24 — SQL Data Transformation Pack.

Recomputes EVERY headline number from data/raw/*_SAMPLE.csv with
the standard library only (no pandas), re-implementing the SQL
cleaning rules in Python (price parse, date parse, category and
channel recode, dedup by latest updated_at, NULL rules). Then it
rebuilds the database from scratch, re-runs all 10 .sql files, and
compares their output row-for-row against the shipped technique
CSVs. It also compares every number in outputs/summary.json,
outputs/findings.md and README.md, and verifies the generator is
deterministic and the build is reproducible.

Run: python3 src/checks.py
Exit code 0 = all checks pass. Any failure is a build bug — fix the
build, never weaken the check.
"""

import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
SQL = ROOT / "sql"

PASSED = 0
FAILED = []


def check(name, ok, detail=""):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILED.append(f"{name} :: {detail}")


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------------- Python mirrors of the SQL cleaning rules --------
def parse_price(text):
    """'Rs. 2,500' / 'Rs.2500' / '2500' / ' ' -> int or None."""
    if text is None or text.strip() == "":
        return None
    return int(text.replace("Rs.", "").replace(",", "").replace(" ", ""))


def parse_date(text):
    """DD/MM/YYYY -> ISO; ISO passes through."""
    if "/" in text:
        d, m, y = text.split("/")
        return f"{y}-{m}-{d}"
    return text


CATEGORY_MAP = {
    "ELECTRONICS": "Electronics", "ELEC.": "Electronics",
    "FURNITURE": "Furniture", "STATIONERY": "Stationery",
    "KITCHEN": "Kitchen",
}


def clean_category(raw):
    return CATEGORY_MAP.get(raw.strip().upper(), "UNMAPPED: " + raw)


CHANNEL_MAP = {"ONLINE": "Online", "INSTORE": "In-Store",
               "PHONE": "Phone"}


def clean_channel(raw):
    key = raw.strip().upper().replace(" ", "").replace("-", "")
    return CHANNEL_MAP.get(key, "UNMAPPED: " + raw)


def proper_name(name):
    words = " ".join(name.split()).split(" ")
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


def clean_city(city):
    city = city.strip()
    if city == "":
        return "Unknown"
    return city[:1].upper() + city[1:].lower()


def dedup(rows, key):
    """Latest row per key by updated_at (stable: last wins on ties)."""
    best = {}
    for r in rows:
        k = r[key]
        if k not in best or r["updated_at"] >= best[k]["updated_at"]:
            best[k] = r
    return best


def main():
    customers = rows(RAW / "customers_raw_SAMPLE.csv")
    products = rows(RAW / "products_raw_SAMPLE.csv")
    orders = rows(RAW / "orders_raw_SAMPLE.csv")
    items = rows(RAW / "order_items_raw_SAMPLE.csv")

    # ================= raw files =================
    check("customers_raw: 15 rows", len(customers) == 15, str(len(customers)))
    check("customers_raw: 12 unique codes",
          len({r["customer_code"] for r in customers}) == 12)
    check("customers_raw: dup codes are 001, 003, 007",
          sorted(c for c in {r["customer_code"] for r in customers}
                 if sum(1 for x in customers
                        if x["customer_code"] == c) > 1)
          == ["CUST-001", "CUST-003", "CUST-007"])
    check("products_raw: 9 rows", len(products) == 9)
    check("products_raw: 9 raw category spellings",
          len({r["category_raw"] for r in products}) == 9,
          str({r["category_raw"] for r in products}))
    check("orders_raw: 34 rows", len(orders) == 34, str(len(orders)))
    check("orders_raw: 32 unique ids",
          len({r["order_id"] for r in orders}) == 32)
    check("orders_raw: dup ids are 7 and 19",
          sorted(o for o in {r["order_id"] for r in orders}
                 if sum(1 for x in orders if x["order_id"] == o) > 1)
          == ["19", "7"])
    check("orders_raw: 11 raw channel spellings",
          len({r["channel_raw"] for r in orders}) == 11,
          str({r["channel_raw"] for r in orders}))
    check("items_raw: 54 rows", len(items) == 54, str(len(items)))
    check("items_raw: 52 unique ids",
          len({r["line_id"] for r in items}) == 52)
    check("items_raw: dup ids are 10 and 25",
          sorted(i for i in {r["line_id"] for r in items}
                 if sum(1 for x in items if x["line_id"] == i) > 1)
          == ["10", "25"])

    # Python-side cleaning (independent of the SQL)
    cust = dedup(customers, "customer_code")
    ords = dedup(orders, "order_id")
    lns = dedup(items, "line_id")
    catalogue = {r["product_code"]: (clean_category(r["category_raw"]),
                                     parse_price(r["price_text"]))
                 for r in products}
    cust_clean = {code: (proper_name(r["name"]), clean_city(r["city"]),
                         parse_date(r["signup_date_text"]))
                  for code, r in cust.items()}

    # clean lines with the NULL rules: qty blank -> 1, price blank ->
    # catalogue price
    clean_lines = []
    for lid, r in sorted(lns.items(), key=lambda kv: int(kv[0])):
        qty = parse_price(r["quantity_text"])
        if qty is None:
            qty = 1
        price = parse_price(r["unit_price_text"])
        if price is None:
            price = catalogue[r["product_code"]][1]
        clean_lines.append({
            "line_id": int(lid), "order_id": int(r["order_id"]),
            "product_code": r["product_code"], "quantity": qty,
            "unit_price_pkr": price, "revenue": qty * price})
    check("clean lines: 52", len(clean_lines) == 52)
    check("clean lines: revenue PKR 346,800",
          sum(l["revenue"] for l in clean_lines) == 346800,
          str(sum(l["revenue"] for l in clean_lines)))
    check("clean lines: 81 units",
          sum(l["quantity"] for l in clean_lines) == 81)

    order_date = {int(oid): parse_date(r["order_date_text"])
                  for oid, r in ords.items()}
    order_channel = {int(oid): clean_channel(r["channel_raw"])
                     for oid, r in ords.items()}
    monthly_rev = defaultdict(int)
    monthly_orders = defaultdict(set)
    cat_rev = defaultdict(int)
    chan_rev = defaultdict(int)
    chan_orders = defaultdict(set)
    for l in clean_lines:
        m = order_date[l["order_id"]][:7]
        c = catalogue[l["product_code"]][0]
        ch = order_channel[l["order_id"]]
        monthly_rev[m] += l["revenue"]
        monthly_orders[m].add(l["order_id"])
        cat_rev[c] += l["revenue"]
        chan_rev[ch] += l["revenue"]
        chan_orders[ch].add(l["order_id"])
    check("monthly revenue",
          dict(monthly_rev) == {"2026-01": 37100, "2026-02": 50000,
                                "2026-03": 30500, "2026-04": 62100,
                                "2026-05": 72900, "2026-06": 94200},
          str(dict(monthly_rev)))
    check("category revenue",
          dict(cat_rev) == {"Electronics": 104000, "Furniture": 105600,
                            "Kitchen": 106000, "Stationery": 31200},
          str(dict(cat_rev)))
    check("channel revenue",
          dict(chan_rev) == {"Online": 116600, "In-Store": 113200,
                             "Phone": 117000},
          str(dict(chan_rev)))
    check("orders by channel",
          {k: len(v) for k, v in chan_orders.items()}
          == {"Online": 11, "In-Store": 10, "Phone": 11})
    check("channel shares",
          {k: round(v / 346800 * 100, 2) for k, v in chan_rev.items()}
          == {"Online": 33.62, "In-Store": 32.64, "Phone": 33.74})
    check("category shares",
          {k: round(v / 346800 * 100, 2) for k, v in cat_rev.items()}
          == {"Kitchen": 30.57, "Furniture": 30.45,
              "Electronics": 29.99, "Stationery": 9.0})

    # ================= fresh DB + re-run every query ==============
    db = ROOT / "data" / "demo.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript((ROOT / "data" / "schema.sql").read_text())
    for table, fname in [("raw_customers", "customers_raw_SAMPLE.csv"),
                         ("raw_products", "products_raw_SAMPLE.csv"),
                         ("raw_orders", "orders_raw_SAMPLE.csv"),
                         ("raw_order_items", "order_items_raw_SAMPLE.csv")]:
        with open(RAW / fname, newline="") as f:
            data = list(csv.reader(f))
        header, body = data[0], data[1:]
        con.executemany(
            f"INSERT INTO {table} VALUES "
            f"({','.join('?' * len(header))})", body)
    con.commit()
    check("DB: raw counts match CSVs",
          {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("raw_customers", "raw_products", "raw_orders",
                     "raw_order_items")}
          == {"raw_customers": 15, "raw_products": 9, "raw_orders": 34,
              "raw_order_items": 54})

    slugs = [
        ("t01", "case_category_price_bands"),
        ("t02", "cast_text_to_numbers"),
        ("t03", "string_cleaning"),
        ("t04", "date_parsing"),
        ("t05", "null_handling"),
        ("t06", "dedup_row_number"),
        ("t07", "pivot_sales_by_channel"),
        ("t08", "conditional_aggregation_kpis"),
        ("t09", "split_order_code"),
        ("t10", "clean_transform_pipeline"),
    ]
    results = {}
    for num, slug in slugs:
        path = SQL / f"{num}_{slug}.sql"
        check(f"sql file exists: {path.name}", path.exists())
        cur = con.execute(path.read_text())
        cols = [d[0] for d in cur.description]
        qrows = cur.fetchall()
        results[num] = (cols, qrows)
        shipped = rows(OUT / f"technique_{num[1:]}_{slug}.csv")
        shipped_t = [tuple(r[c] for c in cols) for r in shipped]
        fresh_t = [tuple("" if v is None else str(v) for v in r)
                   for r in qrows]
        check(f"{num}: shipped CSV matches a fresh query run",
              shipped_t == fresh_t,
              f"shipped {len(shipped_t)} rows, fresh {len(fresh_t)}")

    # ================= technique spot checks =================
    # t01 — CASE recode + price bands
    t01 = {r[0]: r for r in results["t01"][1]}
    check("t01: 9 rows", len(results["t01"][1]) == 9)
    check("t01: 'Elec.' (PRD-09) recodes to Electronics",
          t01["PRD-09"][3] == "Electronics", str(t01["PRD-09"]))
    check("t01: PRD-04 Premium at PKR 18,000",
          t01["PRD-04"][3] == "Furniture" and t01["PRD-04"][4] == 18000
          and t01["PRD-04"][5] == "Premium (PKR 10,000+)",
          str(t01["PRD-04"]))
    check("t01: PRD-06 Budget at PKR 1,200",
          t01["PRD-06"][4] == 1200
          and t01["PRD-06"][5] == "Budget (< PKR 3,000)",
          str(t01["PRD-06"]))
    check("t01: bands are 2 Budget / 5 Mid-range / 2 Premium",
          {b: sum(1 for r in results["t01"][1] if r[5] == b)
           for b in ("Budget (< PKR 3,000)",
                     "Mid-range (PKR 3,000-9,999)",
                     "Premium (PKR 10,000+)")}
          == {"Budget (< PKR 3,000)": 2,
              "Mid-range (PKR 3,000-9,999)": 5,
              "Premium (PKR 10,000+)": 2})
    check("t01: no UNMAPPED categories",
          all("UNMAPPED" not in r[3] for r in results["t01"][1]))

    # t02 — CAST
    t02_by_line = defaultdict(list)
    for r in results["t02"][1]:
        t02_by_line[r[0]].append(r)
    check("t02: 54 rows (raw, duplicates included)",
          len(results["t02"][1]) == 54)
    check("t02: line 20 'Rs. 8,500' -> 8500",
          t02_by_line[20][0][5] == "Rs. 8,500"
          and t02_by_line[20][0][6] == 8500,
          str(t02_by_line[20][0]))
    check("t02: line 3 'Rs. 8,500 ' (trailing space) -> 8500",
          t02_by_line[3][0][5] == "Rs. 8,500 "
          and t02_by_line[3][0][6] == 8500,
          str(t02_by_line[3][0]))
    check("t02: line 9 quantity ' 1 ' -> 1",
          t02_by_line[9][0][3] == " 1 " and t02_by_line[9][0][4] == 1,
          str(t02_by_line[9][0]))
    check("t02: line 1 revenue = 2 x 2500 = 5000",
          t02_by_line[1][0][7] == 5000, str(t02_by_line[1][0]))
    check("t02: line 5 quantity NULL, line 8 price NULL",
          t02_by_line[5][0][4] is None
          and t02_by_line[8][0][6] is None)
    check("t02: exactly 2 NULL quantity/price cells",
          sum(1 for r in results["t02"][1] if r[4] is None)
          + sum(1 for r in results["t02"][1] if r[6] is None) == 2)

    # t03 — string cleaning
    t03 = results["t03"][1]
    check("t03: 15 rows", len(t03) == 15)
    old_ayesha = [r for r in t03 if r[0] == "CUST-001"
                  and r[11] == "2026-01-05"][0]
    check("t03: '  ayesha khan' -> upper AYESHA KHAN, first ayesha",
          old_ayesha[3] == "AYESHA KHAN" and old_ayesha[4] == "ayesha"
          and old_ayesha[5] == "khan", str(old_ayesha))
    hassan = [r for r in t03 if r[0] == "CUST-004"][0]
    check("t03: '  rawalpindi ' -> city_upper RAWALPINDI",
          hassan[8] == "RAWALPINDI", str(hassan))
    fatima_old = [r for r in t03 if r[0] == "CUST-003"
                  and r[11] == "2026-02-01"][0]
    check("t03: blank city -> city_nullif NULL (NULLIF works)",
          fatima_old[9] is None, str(fatima_old))
    check("t03: emails are lower-cased",
          all(r[10] == "" or r[10] == r[10].lower() for r in t03))

    # t04 — date parsing
    t04 = results["t04"][1]
    check("t04: 34 rows", len(t04) == 34)
    check("t04: order 1 '08/01/2026' -> 2026-01-08",
          [r for r in t04 if r[0] == 1][0][3] == "2026-01-08")
    check("t04: order 2 ISO stays 2026-02-14",
          [r for r in t04 if r[0] == 2][0][3] == "2026-02-14")
    check("t04: 17 slash dates, 17 ISO dates",
          sum(1 for r in t04 if "/" in r[2]) == 17
          and sum(1 for r in t04 if "/" not in r[2]) == 17)
    check("t04: 0 invalid dates",
          all(r[5] == "valid" for r in t04))

    # t05 — NULL handling
    t05 = results["t05"][1]
    check("t05: 54 rows", len(t05) == 54)
    line5 = [r for r in t05 if r[0] == 5][0]
    check("t05: line 5 qty NULL -> 1, revenue PKR 18,000",
          line5[5] == 1 and line5[9] == 18000, str(line5))
    line8 = [r for r in t05 if r[0] == 8][0]
    check("t05: line 8 price NULL -> catalogue 14,500, revenue 14,500",
          line8[8] == 14500 and line8[9] == 14500, str(line8))
    check("t05: exactly 2 rows flagged 'fixed NULL'",
          sum(1 for r in t05 if r[10] == "fixed NULL") == 2)
    check("t05: the two fixed lines are worth PKR 32,500",
          sum(r[9] for r in t05 if r[10] == "fixed NULL") == 32500)
    check("t05: fixed lines are 9.37% of clean revenue",
          round(32500 / 346800 * 100, 2) == 9.37)

    # t06 — dedup
    t06 = {r[0]: r for r in results["t06"][1]}
    check("t06: 15 raw rows -> 12 kept", len(results["t06"][1]) == 12)
    check("t06: CUST-001 keeps 'Ayesha Khan' (2026-03-10)",
          t06["CUST-001"][1] == "Ayesha Khan"
          and t06["CUST-001"][5] == "2026-03-10", str(t06["CUST-001"]))
    check("t06: CUST-003 keeps 'Fatima Noor', Islamabad (2026-04-02)",
          t06["CUST-003"][1] == "Fatima Noor"
          and t06["CUST-003"][2] == "Islamabad"
          and t06["CUST-003"][5] == "2026-04-02", str(t06["CUST-003"]))
    check("t06: CUST-007 keeps 'Maryam Siddiqui' (2026-03-20)",
          t06["CUST-007"][1] == "Maryam Siddiqui"
          and t06["CUST-007"][5] == "2026-03-20", str(t06["CUST-007"]))
    check("t06: same ROW_NUMBER pattern dedups orders 34 -> 32",
          con.execute(
              """SELECT COUNT(*) FROM (
                     SELECT order_id, ROW_NUMBER() OVER (
                         PARTITION BY order_id ORDER BY updated_at DESC
                     ) AS rn FROM raw_orders) WHERE rn = 1"""
          ).fetchone()[0] == 32)
    check("t06: same ROW_NUMBER pattern dedups lines 54 -> 52",
          con.execute(
              """SELECT COUNT(*) FROM (
                     SELECT line_id, ROW_NUMBER() OVER (
                         PARTITION BY line_id ORDER BY updated_at DESC
                     ) AS rn FROM raw_order_items) WHERE rn = 1"""
          ).fetchone()[0] == 52)

    # t07 — pivot
    t07 = {r[0]: r for r in results["t07"][1]}
    check("t07: 6 rows (one per month)", len(results["t07"][1]) == 6)
    check("t07: Jan = Online 19,300 / In-Store 11,800 / Phone 6,000",
          t07["2026-01"][1:] == (19300, 11800, 6000, 37100, 5),
          str(t07["2026-01"]))
    check("t07: Jun = Online 25,700 / In-Store 31,000 / Phone 37,500",
          t07["2026-06"][1:] == (25700, 31000, 37500, 94200, 7),
          str(t07["2026-06"]))
    check("t07: every month sells on all 3 channels",
          all(r[1] > 0 and r[2] > 0 and r[3] > 0
              for r in results["t07"][1]))
    check("t07: row totals are the monthly revenue",
          [r[4] for r in results["t07"][1]]
          == [37100, 50000, 30500, 62100, 72900, 94200])
    check("t07: column totals are the channel revenue",
          [sum(r[i] for r in results["t07"][1]) for i in (1, 2, 3)]
          == [116600, 113200, 117000])
    check("t07: orders column sums to 32",
          sum(r[5] for r in results["t07"][1]) == 32)

    # t08 — conditional aggregation
    t08 = {r[0]: r for r in results["t08"][1]}
    check("t08: 4 rows, richest first",
          len(results["t08"][1]) == 4
          and [r[0] for r in results["t08"][1]]
          == ["Kitchen", "Furniture", "Electronics", "Stationery"])
    check("t08: Kitchen PKR 106,000, share 30.57",
          t08["Kitchen"][3] == 106000 and t08["Kitchen"][9] == 30.57,
          str(t08["Kitchen"]))
    check("t08: Furniture avg line PKR 10,560.00, premium 4",
          t08["Furniture"][7] == 10560.0 and t08["Furniture"][8] == 4,
          str(t08["Furniture"]))
    check("t08: Electronics has 19 lines, 0 premium lines",
          t08["Electronics"][1] == 19 and t08["Electronics"][8] == 0,
          str(t08["Electronics"]))
    check("t08: Stationery PKR 31,200, share 9.0",
          t08["Stationery"][3] == 31200 and t08["Stationery"][9] == 9.0,
          str(t08["Stationery"]))
    check("t08: revenues sum to PKR 346,800",
          sum(r[3] for r in results["t08"][1]) == 346800)
    check("t08: premium lines total 8",
          sum(r[8] for r in results["t08"][1]) == 8)
    check("t08: channel splits sum to category revenue",
          all(r[4] + r[5] + r[6] == r[3] for r in results["t08"][1]))

    # t09 — split order code
    t09 = {r[0]: r for r in results["t09"][1]}
    check("t09: 32 rows", len(results["t09"][1]) == 32)
    check("t09: order 1 -> LAH / 1 / Lahore",
          t09[1][1:] == ("LAH-00001", "LAH", 1, "Lahore"), str(t09[1]))
    check("t09: order 28 -> UNK / 28 / Unknown",
          t09[28][1:] == ("UNK-00028", "UNK", 28, "Unknown"),
          str(t09[28]))
    check("t09: 5 UNK orders (12, 13, 23, 24, 28)",
          sorted(r[0] for r in results["t09"][1] if r[2] == "UNK")
          == [12, 13, 23, 24, 28])
    check("t09: every order_no equals its order_id",
          all(r[3] == r[0] for r in results["t09"][1]))

    # t10 — full pipeline / clean mart
    t10 = results["t10"][1]
    check("t10: 52 rows", len(t10) == 52)
    check("t10: revenue sums to PKR 346,800",
          sum(r[14] for r in t10) == 346800,
          str(sum(r[14] for r in t10)))
    check("t10: 32 distinct orders, 10 customers, 8 products",
          len({r[0] for r in t10}) == 32
          and len({r[3] for r in t10}) == 10
          and len({r[9] for r in t10}) == 8)
    check("t10: 0 NULLs in any column",
          all(v is not None for r in t10 for v in r))
    check("t10: 0 unmapped categories or channels",
          all("UNMAPPED" not in r[6] and "UNMAPPED" not in r[11]
              for r in t10))
    check("t10: 5 orders from 'Unknown' city",
          len({r[0] for r in t10 if r[5] == "Unknown"}) == 5)
    check("t10: order 1 line 1 = Ayesha Khan, Lahore, Online, PKR 5,000",
          [r for r in t10 if r[0] == 1 and r[9] == "PRD-01"][0][3:7]
          == ("CUST-001", "Ayesha Khan", "Lahore", "Online")
          and [r for r in t10 if r[0] == 1 and r[9] == "PRD-01"][0][14]
          == 5000)
    check("t10: line 5 fixed by rule (qty 1, PKR 18,000)",
          [r for r in t10 if r[0] == 3 and r[9] == "PRD-04"][0][12:] ==
          (1, 18000, 18000))
    check("t10: line 8 fixed by rule (price PKR 14,500)",
          [r for r in t10 if r[0] == 5 and r[9] == "PRD-08"][0][12:] ==
          (1, 14500, 14500))
    check("t10: every row's revenue = quantity x unit price",
          all(r[12] * r[13] == r[14] for r in t10))
    check("t10: every date is ISO and parses with date()",
          all(r[1] == parse_date(r[1]) and len(r[1]) == 10 for r in t10))
    check("t10: names are proper-case (first letter capital)",
          all(r[4][0].isupper() for r in t10))

    # ================= reconciliation =================
    check("reconciliation: mart revenue = Python clean revenue",
          sum(r[14] for r in t10)
          == sum(l["revenue"] for l in clean_lines) == 346800)
    check("reconciliation: monthly sums = category sums = channel sums",
          sum(monthly_rev.values()) == sum(cat_rev.values())
          == sum(chan_rev.values()) == 346800)
    check("reconciliation: t07 grand total = t08 total = t10 total",
          sum(r[4] for r in results["t07"][1])
          == sum(r[3] for r in results["t08"][1])
          == sum(r[14] for r in t10) == 346800)
    check("reconciliation: mart monthly revenue = Python monthly",
          {m: sum(r[14] for r in t10 if r[2] == m)
           for m in sorted(monthly_rev)}
          == dict(monthly_rev))
    check("reconciliation: mart category revenue = Python category",
          {c: sum(r[14] for r in t10 if r[11] == c)
           for c in sorted(cat_rev)}
          == dict(cat_rev))
    check("reconciliation: mart channel revenue = Python channel",
          {ch: sum(r[14] for r in t10 if r[6] == ch)
           for ch in sorted(chan_rev)}
          == dict(chan_rev))

    # ================= summary.json =================
    summary = json.loads((OUT / "summary.json").read_text())
    exp = {
        "raw_customer_rows": 15, "raw_product_rows": 9,
        "raw_order_rows": 34, "raw_line_rows": 54,
        "clean_customers": 12, "clean_orders": 32, "clean_lines": 52,
        "dedup_removed_customers": 3, "dedup_removed_orders": 2,
        "dedup_removed_lines": 2, "nulls_fixed": 2,
        "clean_revenue_pkr": 346800,
        "distinct_customers_in_mart": 10,
        "distinct_products_in_mart": 8, "unknown_city_orders": 5,
    }
    for k, v in exp.items():
        check(f"summary.json {k} == {v}", summary.get(k) == v,
              f"got {summary.get(k)}")
    check("summary.json monthly revenue",
          summary.get("monthly_revenue_pkr") == dict(monthly_rev))
    check("summary.json channel revenue",
          summary.get("revenue_by_channel_pkr") == dict(chan_rev))
    check("summary.json category revenue",
          summary.get("revenue_by_category_pkr") == dict(cat_rev))
    check("summary.json orders by channel",
          summary.get("orders_by_channel")
          == {"Online": 11, "In-Store": 10, "Phone": 11})
    check("summary.json technique row counts",
          summary.get("technique_rows")
          == {"t01": 9, "t02": 54, "t03": 15, "t04": 34, "t05": 54,
              "t06": 12, "t07": 6, "t08": 4, "t09": 32, "t10": 52})

    # ================= technique CSV headers =================
    exp_headers = {
        "t01": ["product_code", "name", "category_raw", "category_clean",
                "price_pkr", "price_band"],
        "t02": ["line_id", "order_id", "product_code", "quantity_text",
                "quantity_int", "unit_price_text", "unit_price_pkr",
                "line_revenue_pkr"],
        "t03": ["customer_code", "name_raw", "name_trimmed", "name_upper",
                "first_name", "last_name", "city_raw", "city_trimmed",
                "city_upper", "city_nullif", "email_clean", "updated_at"],
        "t04": ["order_id", "customer_code", "order_date_text",
                "order_date_iso", "month", "date_check"],
        "t05": ["line_id", "order_id", "product_code", "quantity_text",
                "quantity_int", "quantity_clean", "unit_price_text",
                "unit_price_int", "unit_price_clean", "line_revenue_pkr",
                "null_flag"],
        "t06": ["customer_code", "name", "city", "signup_date_text",
                "email", "updated_at"],
        "t07": ["month", "online_pkr", "in_store_pkr", "phone_pkr",
                "total_pkr", "orders"],
        "t08": ["category", "lines", "orders", "revenue_pkr",
                "online_pkr", "in_store_pkr", "phone_pkr",
                "avg_line_pkr", "premium_lines", "share_pct"],
        "t09": ["order_id", "order_code", "city_code", "order_no",
                "city_name"],
        "t10": ["order_id", "order_date", "month", "customer_code",
                "customer_name", "city", "channel", "order_code",
                "city_code", "product_code", "product_name", "category",
                "quantity", "unit_price_pkr", "line_revenue_pkr"],
    }
    for num, slug in slugs:
        got = list(rows(OUT / f"technique_{num[1:]}_{slug}.csv")[0].keys())
        check(f"technique {num} CSV header", got == exp_headers[num],
              f"got {got}")

    # ================= findings.md / README.md =================
    findings = (OUT / "findings.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for label, text in [("findings.md", findings), ("README.md", readme)]:
        for needle in ["SAMPLE", "346,800", "116,600", "117,000",
                       "113,200", "32,500", "9.37", "106,000",
                       "105,600", "104,000", "31,200", "37,100",
                       "94,200", "30.57", "10,560.00", "18,000",
                       "14,500", "52", "32", "12"]:
            check(f"{label} contains {needle!r}", needle in text)
        check(f"{label} never claims real client work",
              "real client" not in text.lower()
              or "never claimed as real client work" in text.lower())
    check("README contains the demand signal (11.3%)",
          "11.3%" in readme)
    check("README contains Data Modelling 19.5–22%",
          "19.5" in readme)
    check("findings.md states the NULL rules",
          "missing quantity counts as 1" in findings
          and "catalogue price" in findings)

    # ================= generator determinism =================
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "generate_data.py"),
             "--out-dir", str(td)],
            capture_output=True, text=True)
        check("generator re-runs cleanly", proc.returncode == 0,
              proc.stderr[-300:])
        if proc.returncode == 0:
            for src in sorted(RAW.glob("*.csv")):
                regen = td / src.name
                check(f"generator deterministic: {src.name}",
                      regen.exists()
                      and hashlib.sha256(src.read_bytes()).hexdigest()
                      == hashlib.sha256(regen.read_bytes()).hexdigest())

    # ================= build reproducibility =================
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.glob("technique_*.csv"))}
    before_sum = hashlib.sha256(
        (OUT / "summary.json").read_bytes()).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "build.py")],
        capture_output=True, text=True, cwd=str(ROOT))
    check("build.py re-runs cleanly", proc.returncode == 0,
          proc.stderr[-300:])
    if proc.returncode == 0:
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(OUT.glob("technique_*.csv"))}
        check("build is reproducible (technique CSVs stable)",
              after == before)
        check("build is reproducible (summary.json stable)",
              hashlib.sha256(
                  (OUT / "summary.json").read_bytes()).hexdigest()
              == before_sum)

    # ================= repo furniture =================
    check("requirements.txt says standard library only",
          "Standard library only" in (ROOT / "requirements.txt").read_text())
    check(".gitignore excludes *.db",
          "*.db" in (ROOT / ".gitignore").read_text())
    check("data/README.md exists", (ROOT / "data" / "README.md").exists())
    check("data/schema.sql exists", (ROOT / "data" / "schema.sql").exists())
    check("run_tests.py exists", (ROOT / "src" / "run_tests.py").exists())
    check("all 10 sql files exist",
          len(list(SQL.glob("t*.sql"))) == 10)
    check("all 10 technique CSVs exist",
          len(list(OUT.glob("technique_*.csv"))) == 10)
    check("no technique CSV is empty",
          all(p.stat().st_size > 0
              for p in OUT.glob("technique_*.csv")))

    print(f"{PASSED} checks passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print(" -", f)

    (OUT / "test_results.json").write_text(json.dumps({
        "checks_passed": PASSED,
        "checks_failed": len(FAILED),
        "failed": FAILED,
        "total": PASSED + len(FAILED),
    }, indent=2) + "\n")
    print(f"wrote outputs/test_results.json "
          f"({PASSED} passed, {len(FAILED)} failed)")
    con.close()
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
