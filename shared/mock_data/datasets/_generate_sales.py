"""
Utility script to regenerate sales_transactions_2023_2024.csv.
Run from the repo root: python shared/mock_data/datasets/_generate_sales.py
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)

PRODUCTS = [
    ("P001", "Cloud License Annual",       2000.00),
    ("P002", "Support Package Premium",    1500.00),
    ("P003", "Data Analytics Module",      5000.00),
    ("P004", "Implementation Services",     500.00),  # per unit = 1 hr
    ("P005", "Training & Enablement",       800.00),
]

REGIONS = ["Northeast", "West", "Southeast", "Midwest", "Southwest"]
REGION_WEIGHTS = [0.30, 0.25, 0.18, 0.15, 0.12]

INDUSTRIES = ["Financial Services", "Healthcare", "Technology", "Manufacturing", "Retail"]

SALES_REPS = [
    "Jordan Alvarez",
    "Priya Nair",
    "Marcus Webb",
    "Tanya Collins",
    "Derek Huang",
]

PAYMENT_METHODS = ["ACH Transfer", "Wire Transfer", "Corporate Card", "Check"]

CUSTOMERS = [
    ("C001", "Apex Financial Group",     "Financial Services", "Northeast"),
    ("C002", "BlueStar Health Systems",  "Healthcare",         "Southeast"),
    ("C003", "Cascade Technologies",     "Technology",         "West"),
    ("C004", "DataVault Inc.",           "Technology",         "Northeast"),
    ("C005", "Evergreen Manufacturing",  "Manufacturing",      "Midwest"),
    ("C006", "FinEdge Capital",          "Financial Services", "Southwest"),
    ("C007", "GridCore Energy",          "Manufacturing",      "Southwest"),
    ("C008", "Harbor Retail Group",      "Retail",             "Southeast"),
    ("C009", "InnovateMed LLC",          "Healthcare",         "West"),
    ("C010", "Junction Analytics",       "Technology",         "Midwest"),
    ("C011", "KeyStone Advisors",        "Financial Services", "Northeast"),
    ("C012", "Luminary Data Co.",        "Technology",         "West"),
    ("C013", "Momentum Capital",         "Financial Services", "Northeast"),
    ("C014", "NorthStar Logistics",      "Manufacturing",      "Midwest"),
    ("C015", "Orbit Health Partners",    "Healthcare",         "Southeast"),
    ("C016", "Pinnacle Insurance",       "Financial Services", "Northeast"),
    ("C017", "QuantumLeap Systems",      "Technology",         "West"),
    ("C018", "RedRock Mining Corp",      "Manufacturing",      "Southwest"),
    ("C019", "Summit Retail Partners",   "Retail",             "Midwest"),
    ("C020", "Titan Financial LLC",      "Financial Services", "Southeast"),
]

FISCAL_QUARTER_MAP = {
    1: "Q1", 2: "Q1", 3: "Q1",
    4: "Q2", 5: "Q2", 6: "Q2",
    7: "Q3", 8: "Q3", 9: "Q3",
    10: "Q4", 11: "Q4", 12: "Q4",
}

def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def get_region_weight_for_customer(region):
    # Boost Northeast/West, moderate rest
    weights = {"Northeast": 0.30, "West": 0.25, "Southeast": 0.18, "Midwest": 0.15, "Southwest": 0.12}
    return weights.get(region, 0.15)

def q4_weight(dt):
    # Q4 months get 1.6x transaction probability
    return 1.6 if dt.month in (10, 11, 12) else 1.0

rows = []
tx_id = 1

start_date = date(2023, 1, 1)
end_date = date(2024, 3, 31)

# Generate base volume — target ~520 rows
target = 520
while len(rows) < target:
    # Pick a random customer
    customer = random.choice(CUSTOMERS)
    c_id, c_name, c_industry, c_region = customer

    # Slightly weight Northeast/West customers
    if random.random() > get_region_weight_for_customer(c_region) * 2.5:
        continue

    # Pick a product
    product = random.choice(PRODUCTS)
    p_id, p_name, unit_price = product

    # Quantity: Implementation Services sold in hours (2–40), others 1–5
    if p_id == "P004":
        qty = random.randint(2, 40)
    elif p_id == "P003":
        qty = random.randint(1, 3)
    else:
        qty = random.randint(1, 5)

    total = round(qty * unit_price, 2)

    # Date — bias toward Q4
    dt = random_date(start_date, end_date)
    if random.random() < 0.25 and dt.month not in (10, 11, 12):
        # Retry for Q4 to increase density
        dt = random_date(date(2023, 10, 1), date(2023, 12, 31))

    fiscal_year = dt.year
    if dt.month < 4:
        fiscal_year = dt.year  # calendar-aligned for simplicity
    fq = f"{FISCAL_QUARTER_MAP[dt.month]} {fiscal_year}"

    # Status distribution: 85% Completed, 10% Pending, 5% Cancelled
    r = random.random()
    if r < 0.85:
        status = "Completed"
    elif r < 0.95:
        status = "Pending"
    else:
        status = "Cancelled"

    # Sales rep — assign rep based on region loosely
    rep = random.choice(SALES_REPS)
    payment = random.choice(PAYMENT_METHODS)

    rows.append({
        "transaction_id": f"TXN-{tx_id:05d}",
        "date": dt.strftime("%Y-%m-%d"),
        "product_id": p_id,
        "product_name": p_name,
        "quantity": qty,
        "unit_price": unit_price,
        "total_amount": total,
        "customer_id": c_id,
        "customer_name": c_name,
        "industry": c_industry,
        "region": c_region,
        "sales_rep": rep,
        "payment_method": payment,
        "status": status,
        "fiscal_quarter": fq,
    })
    tx_id += 1

# Sort by date
rows.sort(key=lambda r: r["date"])
# Re-assign sequential IDs after sort
for i, row in enumerate(rows, 1):
    row["transaction_id"] = f"TXN-{i:05d}"

fieldnames = [
    "transaction_id", "date", "product_id", "product_name", "quantity",
    "unit_price", "total_amount", "customer_id", "customer_name",
    "industry", "region", "sales_rep", "payment_method", "status", "fiscal_quarter",
]

import os
out_path = os.path.join(os.path.dirname(__file__), "sales_transactions_2023_2024.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows -> {out_path}")
