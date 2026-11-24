"""Build Mini #24 — SQL Data Transformation Pack.

1. Rebuilds data/demo.db from scratch: runs data/schema.sql, then
   loads the 4 raw SAMPLE CSVs verbatim (empty fields stay empty
   strings — the SQL turns blanks into NULL with NULLIF).
2. Runs sql/t01..t10 in order against the fresh DB.
3. Writes one CSV per technique to outputs/technique_NN_<slug>.csv
   (the expected output of each .sql file) and outputs/summary.json
   (every headline number, machine-readable).

Run: python3 src/build.py
The .db is rebuildable from the pushed scripts and is NOT uploaded
to GitHub (see .gitignore).
"""

import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SQL = ROOT / "sql"
OUT = ROOT / "outputs"

TECHNIQUES = [
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

LOAD = [
    ("raw_customers", "customers_raw_SAMPLE.csv"),
    ("raw_products", "products_raw_SAMPLE.csv"),
    ("raw_orders", "orders_raw_SAMPLE.csv"),
    ("raw_order_items", "order_items_raw_SAMPLE.csv"),
]


def build_db():
    db = DATA / "demo.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript((DATA / "schema.sql").read_text())
    for table, fname in LOAD:
        with open(DATA / "raw" / fname, newline="") as f:
            rows = list(csv.reader(f))
        header, data = rows[0], rows[1:]
        con.executemany(
            f"INSERT INTO {table} VALUES ({','.join('?' * len(header))})",
            data)
    con.commit()
    return con


def main():
    OUT.mkdir(exist_ok=True)
    con = build_db()

    raw_counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t, _ in LOAD}
    print("raw rows:", raw_counts)

    results = {}
    for num, slug in TECHNIQUES:
        path = SQL / f"{num}_{slug}.sql"
        cur = con.execute(path.read_text())
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        results[num] = (cols, rows)
        out_path = OUT / f"technique_{num[1:]}_{slug}.csv"
        with open(out_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"ran {path.name}: {len(rows)} rows -> {out_path.name}")

    # ---- headline numbers, all derived from the query results ----
    t07 = results["t07"][1]   # month, online, in-store, phone, total, orders
    t08 = results["t08"][1]   # category, lines, orders, revenue, ...
    t10 = results["t10"][1]   # mart rows
    monthly = {r[0]: r[4] for r in t07}
    channel = {
        "Online": sum(r[1] for r in t07),
        "In-Store": sum(r[2] for r in t07),
        "Phone": sum(r[3] for r in t07),
    }
    category = {r[0]: r[3] for r in t08}
    clean_revenue = sum(r[14] for r in t10)
    summary = {
        "raw_customer_rows": raw_counts["raw_customers"],
        "raw_product_rows": raw_counts["raw_products"],
        "raw_order_rows": raw_counts["raw_orders"],
        "raw_line_rows": raw_counts["raw_order_items"],
        "clean_customers": len(results["t06"][1]),
        "clean_orders": len({r[0] for r in t10}),
        "clean_lines": len(t10),
        "dedup_removed_customers": raw_counts["raw_customers"]
        - len(results["t06"][1]),
        "dedup_removed_orders": raw_counts["raw_orders"]
        - len({r[0] for r in results["t09"][1]}),
        "dedup_removed_lines": raw_counts["raw_order_items"] - len(t10),
        "nulls_fixed": sum(1 for r in results["t05"][1]
                           if r[10] == "fixed NULL"),
        "clean_revenue_pkr": clean_revenue,
        "monthly_revenue_pkr": monthly,
        "revenue_by_channel_pkr": channel,
        "revenue_by_category_pkr": category,
        "technique_rows": {num: len(results[num][1])
                           for num, _ in TECHNIQUES},
        "distinct_customers_in_mart": len({r[3] for r in t10}),
        "distinct_products_in_mart": len({r[9] for r in t10}),
        "unknown_city_orders": len({r[0] for r in t10 if r[5] == "Unknown"}),
        "months": sorted(monthly),
    }
    # orders per channel: one channel per order, read off the mart.
    seen = {}
    for r in t10:
        seen[r[0]] = r[6]
    summary["orders_by_channel"] = {
        ch: sum(1 for v in seen.values() if v == ch)
        for ch in ("Online", "In-Store", "Phone")
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote outputs/summary.json")
    print(f"clean mart: {len(t10)} lines, "
          f"PKR {clean_revenue:,} revenue, "
          f"{len({r[0] for r in t10})} orders")
    con.close()


if __name__ == "__main__":
    main()
