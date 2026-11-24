"""Regenerate the SAMPLE data for Mini #24 — SQL Data Transformation Pack.

Writes the deliberately MESSY bronze layer for the fictional "Noor
Electronics" shop — the same shop, customers, products, orders and
lines as Mini #1 / #3 / #15 / #22 / #23 (32 orders, 52 lines,
PKR 346,800 once cleaned), but with the mess real source systems
actually send:

- mixed-case names with leading/trailing/double spaces
- price text: "Rs. 2,500" / "Rs.2500" / "2500" / trailing spaces
- dates in both ISO (2026-01-08) and DD/MM/YYYY (08/01/2026)
- category spellings: "electronics", "Electronics ", "ELECTRONICS",
  "Elec." — all the same category
- channel spellings: "online", "Online", "ONLINE", "in-store",
  "In Store", "instore", "phone"
- empty fields (loaded as-is; SQL turns them into NULL with NULLIF)
- duplicate source rows (same key, older updated_at) for the dedup
  technique: 15 customer rows -> 12 customers, 34 order rows ->
  32 orders, 54 line rows -> 52 lines

Everything is hard-coded literals: deterministic, no randomness, no
network. Re-running produces byte-identical files. The mess is
formatting only — every value parses back to the clean base, so the
clean mart (technique 10) must reconcile exactly to PKR 346,800.

Run: python3 src/generate_data.py [--out-dir DIR]
"""

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# ------------------------------------------------------------------
# customers: 15 raw rows, 12 unique codes.
# (customer_code, name, city, signup_date_text, email, updated_at)
# Empty string = the source sent a blank field (stays blank in the
# CSV/DB; the SQL turns blanks into NULL with NULLIF).
# ------------------------------------------------------------------
CUSTOMERS = [
    ("CUST-001", "  ayesha khan", "lahore", "05/01/2026", "", "2026-01-05"),
    ("CUST-001", "Ayesha Khan", "Lahore", "2026-01-05", "ayesha@example.pk",
     "2026-03-10"),
    ("CUST-002", "bilal ahmed", "Karachi", "2026-01-12", "bilal@example.pk",
     "2026-01-12"),
    ("CUST-003", "FATIMA NOOR", "", "12/02/2026", "", "2026-02-01"),
    ("CUST-003", "Fatima Noor", "Islamabad", "2026-02-12",
     "fatima@example.pk", "2026-04-02"),
    ("CUST-004", "Hassan Raza", "  rawalpindi ", "2026-01-20",
     "hassan@example.pk", "2026-01-20"),
    ("CUST-005", "zainab ali", "", "03/02/2026", "zainab@example.pk",
     "2026-02-03"),
    ("CUST-006", "Usman Tariq", "Peshawar", "2026-02-10", "",
     "2026-02-10"),
    ("CUST-007", "maryam siddiqui", "lahore", "15/03/2026",
     "maryam@example.pk", "2026-03-15"),
    ("CUST-007", "Maryam Siddiqui", "Lahore", "2026-03-15",
     "maryam@example.pk", "2026-03-20"),
    ("CUST-008", "Ali Nawaz", "Multan", "2026-03-22", "ali@example.pk",
     "2026-03-22"),
    ("CUST-009", "SARA MALIK", "Faisalabad", "10/04/2026", "",
     "2026-04-10"),
    ("CUST-010", "Omar Farooq", "", "2026-04-18", "omar@example.pk",
     "2026-04-18"),
    ("CUST-011", "Hina Shah", "Quetta", "2026-05-05", "hina@example.pk",
     "2026-05-05"),
    ("CUST-012", "Danish Iqbal", "Hyderabad", "20/05/2026",
     "danish@example.pk", "2026-05-20"),
]

# ------------------------------------------------------------------
# products: 9 rows. (product_code, name, category_raw, price_text)
# ------------------------------------------------------------------
PRODUCTS = [
    ("PRD-01", "Wireless Mouse", "electronics", "Rs. 2,500"),
    ("PRD-02", "Mechanical Keyboard", "Electronics ", "Rs. 8,500"),
    ("PRD-03", "Laptop Stand", "ELECTRONICS", "Rs. 4,500"),
    ("PRD-04", "Office Chair", "Furniture", "Rs. 18,000"),
    ("PRD-05", "Desk Lamp", "furniture", "Rs. 4,200"),
    ("PRD-06", "Notebook Set", "stationery", "Rs. 1,200"),
    ("PRD-07", "Ceramic Mug Set", "Kitchen", "Rs. 3,200"),
    ("PRD-08", "Dinner Set 24pc", "kitchen ", "Rs. 14,500"),
    ("PRD-09", "Bluetooth Speaker", "Elec.", "Rs. 6,500"),
]

# Clean base orders (Mini #23): (order_id, customer_id, order_date).
# customer_id maps to CUST-001..CUST-012. Odd order_ids get the
# DD/MM/YYYY form, even order_ids stay ISO — 16 of each.
ORDERS_CLEAN = [
    (1, 1, "2026-01-08"), (2, 1, "2026-02-14"), (3, 1, "2026-04-02"),
    (4, 2, "2026-01-15"), (5, 2, "2026-03-20"), (6, 2, "2026-05-11"),
    (7, 3, "2026-01-22"), (8, 3, "2026-02-28"), (9, 3, "2026-06-05"),
    (10, 4, "2026-02-05"), (11, 4, "2026-04-18"), (12, 5, "2026-02-12"),
    (13, 5, "2026-05-25"), (14, 6, "2026-03-03"), (15, 6, "2026-03-29"),
    (16, 6, "2026-06-12"), (17, 7, "2026-03-15"), (18, 7, "2026-04-22"),
    (19, 8, "2026-01-30"), (20, 8, "2026-05-08"), (21, 9, "2026-04-10"),
    (22, 9, "2026-06-20"), (23, 10, "2026-04-15"), (24, 10, "2026-05-30"),
    (25, 1, "2026-06-18"), (26, 2, "2026-06-25"), (27, 4, "2026-06-02"),
    (28, 5, "2026-01-19"), (29, 7, "2026-06-28"), (30, 8, "2026-02-21"),
    (31, 9, "2026-02-08"), (32, 3, "2026-05-14"),
]

# City code per customer (deduped/latest city; NULL city -> UNK),
# used to build the composite order_code "LAH-00001".
CITY_CODE = {
    1: "LAH", 2: "KHI", 3: "ISB", 4: "RWP", 5: "UNK", 6: "PEW",
    7: "LAH", 8: "MUX", 9: "FSD", 10: "UNK", 11: "QUE", 12: "HYD",
}

# Channel per order, hand-assigned so every month sells on all three
# channels (a modulo rule would tie channel to order_id, and order
# ids run roughly in date order — January would come out 100%
# Online). Totals: 11 Online, 10 In-Store, 11 Phone.
CHANNEL_BY_ORDER = {
    1: "Online", 2: "Phone", 3: "Phone", 4: "In-Store", 5: "In-Store",
    6: "Online", 7: "Phone", 8: "Online", 9: "In-Store", 10: "In-Store",
    11: "In-Store", 12: "Phone", 13: "Phone", 14: "Online",
    15: "Phone", 16: "Phone", 17: "Online", 18: "Online",
    19: "Online", 20: "In-Store", 21: "Phone", 22: "Online",
    23: "In-Store", 24: "Online", 25: "In-Store", 26: "Phone",
    27: "Online", 28: "In-Store", 29: "Phone", 30: "Online",
    31: "In-Store", 32: "Phone",
}

# Raw spellings each channel arrives in.
CHANNEL_VARIANTS = {
    "Online": ["online", "Online", "ONLINE", "online "],
    "In-Store": ["in-store", "In Store", "instore", "In-Store"],
    "Phone": ["phone", "Phone", "PHONE"],
}


def messy_date(iso, order_id):
    """Odd order_ids: DD/MM/YYYY. Even order_ids: ISO as-is."""
    if order_id % 2 == 1:
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"
    return iso


def build_orders():
    """34 raw order rows: the 32 clean orders + 2 stale duplicates
    (orders 7 and 19, older updated_at, different raw spellings)."""
    rows = []
    for oid, cid, iso in ORDERS_CLEAN:
        code = f"CUST-{cid:03d}"
        order_code = f"{CITY_CODE[cid]}-{oid:05d}"
        channel = CHANNEL_BY_ORDER[oid]
        variants = CHANNEL_VARIANTS[channel]
        channel_raw = variants[oid % len(variants)]
        rows.append((oid, code, messy_date(iso, oid), channel_raw,
                     order_code, "2026-06-30"))
    # Stale duplicates: same order_id, older updated_at, messier text.
    # The dedup (technique 6) must keep the 2026-06-30 row, not these.
    rows.append((7, "CUST-003", "22/01/2026", "ONLINE", "ISB-00007",
                 "2026-02-01"))
    rows.append((19, "CUST-008", "2026-01-30", "In Store", "MUX-00019",
                 "2026-02-01"))
    rows.sort(key=lambda r: (r[0], r[5]))
    return rows


# Clean base lines (Mini #23):
# (line_id, order_id, product_id, quantity, unit_price_pkr)
ITEMS_CLEAN = [
    (1, 1, 1, 2, 2500), (2, 1, 6, 3, 1200), (3, 2, 2, 1, 8500),
    (4, 2, 7, 2, 3200), (5, 3, 4, 1, 18000), (6, 4, 1, 1, 2500),
    (7, 4, 3, 1, 4500), (8, 5, 8, 1, 14500), (9, 6, 2, 1, 8500),
    (10, 6, 5, 2, 4200), (11, 7, 6, 5, 1200), (12, 8, 1, 2, 2500),
    (13, 8, 7, 1, 3200), (14, 9, 3, 1, 4500), (15, 9, 8, 1, 14500),
    (16, 10, 5, 1, 4200), (17, 11, 4, 1, 18000), (18, 11, 6, 2, 1200),
    (19, 12, 7, 3, 3200), (20, 13, 2, 1, 8500), (21, 13, 1, 1, 2500),
    (22, 14, 6, 4, 1200), (23, 15, 1, 1, 2500), (24, 15, 5, 1, 4200),
    (25, 16, 8, 1, 14500), (26, 17, 3, 1, 4500), (27, 18, 2, 1, 8500),
    (28, 18, 7, 2, 3200), (29, 19, 1, 3, 2500), (30, 20, 4, 1, 18000),
    (31, 21, 6, 2, 1200), (32, 22, 8, 1, 14500), (33, 22, 5, 1, 4200),
    (34, 23, 7, 2, 3200), (35, 24, 2, 1, 8500), (36, 25, 5, 2, 4200),
    (37, 25, 6, 3, 1200), (38, 26, 1, 2, 2500), (39, 27, 3, 1, 4500),
    (40, 27, 1, 1, 2500), (41, 28, 6, 4, 1200), (42, 29, 4, 1, 18000),
    (43, 30, 5, 1, 4200), (44, 30, 7, 1, 3200), (45, 31, 1, 1, 2500),
    (46, 32, 2, 1, 8500), (47, 32, 6, 2, 1200), (48, 1, 7, 1, 3200),
    (49, 6, 7, 1, 3200), (50, 10, 7, 1, 3200), (51, 20, 6, 1, 1200),
    (52, 24, 7, 1, 3200),
]

PRICE_FORMATS = [
    lambda p: f"Rs. {p:,}",
    lambda p: f"Rs.{p:,}",
    lambda p: f"{p:,}",
    lambda p: f"Rs. {p:,} ",
]


def build_items():
    """54 raw line rows: the 52 clean lines + 2 stale duplicates
    (lines 10 and 25). Two planted NULLs: line 5 has no quantity
    (rule: treat as 1), line 8 has no price (rule: catalogue price).
    Every third line's quantity carries surrounding spaces."""
    rows = []
    for lid, oid, pid, qty, price in ITEMS_CLEAN:
        qty_text = f" {qty} " if lid % 9 == 0 else str(qty)
        if lid == 5:
            qty_text = ""  # NULL quantity -> COALESCE to 1
        price_text = PRICE_FORMATS[lid % 4](price)
        if lid == 8:
            price_text = ""  # NULL price -> COALESCE to catalogue price
        rows.append((lid, oid, f"PRD-{pid:02d}", qty_text, price_text,
                     "2026-06-30"))
    # Stale duplicates: same line_id, older updated_at, different text.
    rows.append((10, 6, "PRD-05", "2", "4200", "2026-02-01"))
    rows.append((25, 16, "PRD-08", "1", "Rs.14500", "2026-02-01"))
    rows.sort(key=lambda r: (r[0], r[5]))
    return rows


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main(out_dir=None):
    out = Path(out_dir) if out_dir else RAW
    orders = build_orders()
    items = build_items()
    write_csv(out / "customers_raw_SAMPLE.csv",
              ["customer_code", "name", "city", "signup_date_text",
               "email", "updated_at"], CUSTOMERS)
    write_csv(out / "products_raw_SAMPLE.csv",
              ["product_code", "name", "category_raw", "price_text"],
              PRODUCTS)
    write_csv(out / "orders_raw_SAMPLE.csv",
              ["order_id", "customer_code", "order_date_text",
               "channel_raw", "order_code", "updated_at"], orders)
    write_csv(out / "order_items_raw_SAMPLE.csv",
              ["line_id", "order_id", "product_code", "quantity_text",
               "unit_price_text", "updated_at"], items)
    total = sum(q * p for _, _, _, q, p in ITEMS_CLEAN)
    print(f"wrote 4 files to {out}")
    print(f"customers_raw={len(CUSTOMERS)} (12 unique codes) "
          f"products_raw={len(PRODUCTS)} orders_raw={len(orders)} "
          f"(32 unique ids) lines_raw={len(items)} (52 unique ids) "
          f"clean_revenue=PKR {total:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    main(ap.parse_args().out_dir)
