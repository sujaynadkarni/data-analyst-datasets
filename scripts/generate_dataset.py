#!/usr/bin/env python3
"""
Messy multi-table dataset generator for data-analyst practice.

Produces a realistic star schema (1 fact + 4 dimensions + 1 bridge) for a chosen
industry, with intentional data-quality issues, join traps, and validation
violations baked in. Also emits an entity-relationship summary, a data
dictionary, and a 10-task analyst exercise list.

Standard library only -- no pip install required. Runs on Python 3.8+.

Usage:
    python generate_dataset.py --industry "Retail & E-Commerce" --rows 1000000 --out ./output
    python generate_dataset.py --config my_profile.json --rows 50000 --out ./output
    python generate_dataset.py --list   # show built-in industry presets

The fact-table row count is tunable with --rows (default 1,000,000). Dimension
tables scale per spec (800-1200 customers, 150-300 products, etc.) regardless of
--rows. Everything is deterministic given --seed.
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta

# --------------------------------------------------------------------------- #
# Built-in industry presets. Each profile supplies only the *vocabulary* that
# makes the data feel like a given industry; the generator mechanics (messiness,
# joins, volume) are identical across industries. For an industry NOT listed
# here, hand the script a --config JSON with the same shape (see references).
# --------------------------------------------------------------------------- #
PRESETS = {
    "retail": {
        "industry": "Retail & E-Commerce",
        "fact_table": "fact_orders", "fact_record": "order", "date_col": "order_date",
        "secondary_date_col": "ship_date", "amount_col": "order_amount",
        "statuses": ["Completed", "Pending", "Cancelled", "Returned", "Shipped"],
        "customer": {"table": "dim_customers", "noun": "customer", "id_dim": "cust_id",
                     "id_fact": "customer_id", "id_prefix": "CUST",
                     "segments": ["Consumer", "Corporate", "Home Office", "Guest"],
                     "statuses": ["Active", "Churned", "Prospect", "VIP"],
                     "adult_required": False},
        "product": {"table": "dim_products", "noun": "product", "id": "product_id",
                    "id_prefix": "PROD", "name_col": "product_name",
                    "categories": {"Furniture": ["Chairs", "Tables", "Bookcases"],
                                   "Technology": ["Phones", "Accessories", "Copiers"],
                                   "Office Supplies": ["Binders", "Paper", "Storage"]}},
        "rep": {"table": "dim_reps", "id": "rep_id", "id_prefix": "REP",
                "name_col": "rep_name", "role": "Sales Rep",
                "teams": ["East", "West", "Central", "South"]},
    },
    "healthcare": {
        "industry": "Healthcare & Hospitals",
        "fact_table": "fact_claims", "fact_record": "claim", "date_col": "service_date",
        "secondary_date_col": "paid_date", "amount_col": "claim_amount",
        "statuses": ["Paid", "Denied", "Pending", "Appealed", "Completed"],
        "customer": {"table": "dim_patients", "noun": "patient", "id_dim": "patient_id",
                     "id_fact": "patient_id", "id_prefix": "PAT",
                     "segments": ["Inpatient", "Outpatient", "Emergency", "Guest"],
                     "statuses": ["Active", "Discharged", "Deceased", "Transferred"],
                     "adult_required": True},
        "product": {"table": "dim_procedures", "noun": "procedure", "id": "procedure_id",
                    "id_prefix": "PROC", "name_col": "procedure_name",
                    "categories": {"Cardiology": ["Imaging", "Surgery", "Diagnostics"],
                                   "Orthopedics": ["Imaging", "Surgery", "Therapy"],
                                   "General": ["Lab", "Consultation", "Vaccination"]}},
        "rep": {"table": "dim_providers", "id": "provider_id", "id_prefix": "PRV",
                "name_col": "provider_name", "role": "Physician",
                "teams": ["Cardiology", "Orthopedics", "General Medicine", "Emergency"]},
    },
    "finance": {
        "industry": "Finance & Banking",
        "fact_table": "fact_transactions", "fact_record": "transaction", "date_col": "txn_date",
        "secondary_date_col": "settle_date", "amount_col": "txn_amount",
        "statuses": ["Completed", "Pending", "Reversed", "Flagged", "Declined"],
        "customer": {"table": "dim_accounts", "noun": "account", "id_dim": "acct_id",
                     "id_fact": "account_id", "id_prefix": "ACCT",
                     "segments": ["Retail", "Premier", "Business", "Guest"],
                     "statuses": ["Active", "Dormant", "Closed", "Frozen"],
                     "adult_required": True},
        "product": {"table": "dim_products", "noun": "product", "id": "product_id",
                    "id_prefix": "FPRD", "name_col": "product_name",
                    "categories": {"Deposits": ["Checking", "Savings", "CD"],
                                   "Credit": ["Card", "Line", "Mortgage"],
                                   "Investments": ["Brokerage", "Retirement", "Fund"]}},
        "rep": {"table": "dim_bankers", "id": "banker_id", "id_prefix": "BNK",
                "name_col": "banker_name", "role": "Relationship Manager",
                "teams": ["Retail", "Commercial", "Wealth", "Lending"]},
    },
    "manufacturing": {
        "industry": "Manufacturing & Supply Chain",
        "fact_table": "fact_production_orders", "fact_record": "production order",
        "date_col": "order_date", "secondary_date_col": "completion_date",
        "amount_col": "order_value",
        "statuses": ["Completed", "In Progress", "Cancelled", "On Hold", "Shipped"],
        "customer": {"table": "dim_customers", "noun": "customer", "id_dim": "cust_id",
                     "id_fact": "customer_id", "id_prefix": "CUST",
                     "segments": ["OEM", "Distributor", "Retail", "Guest"],
                     "statuses": ["Active", "Inactive", "Prospect", "Preferred"],
                     "adult_required": False},
        "product": {"table": "dim_parts", "noun": "part", "id": "part_id",
                    "id_prefix": "PART", "name_col": "part_name",
                    "categories": {"Assemblies": ["Welded", "Machined", "Cast"],
                                   "Components": ["Fasteners", "Bearings", "Seals"],
                                   "Raw": ["Steel", "Aluminum", "Polymer"]}},
        "rep": {"table": "dim_planners", "id": "planner_id", "id_prefix": "PLN",
                "name_col": "planner_name", "role": "Production Planner",
                "teams": ["Line A", "Line B", "Line C", "Fulfillment"]},
    },
    "logistics": {
        "industry": "Logistics & Shipping",
        "fact_table": "fact_shipments", "fact_record": "shipment", "date_col": "pickup_date",
        "secondary_date_col": "delivery_date", "amount_col": "freight_cost",
        "statuses": ["Delivered", "In Transit", "Cancelled", "Delayed", "Completed"],
        "customer": {"table": "dim_shippers", "noun": "shipper", "id_dim": "shipper_id",
                     "id_fact": "shipper_id", "id_prefix": "SHP",
                     "segments": ["Enterprise", "SMB", "Individual", "Guest"],
                     "statuses": ["Active", "Churned", "Prospect", "Contract"],
                     "adult_required": False},
        "product": {"table": "dim_services", "noun": "service", "id": "service_id",
                    "id_prefix": "SVC", "name_col": "service_name",
                    "categories": {"Ground": ["Standard", "Expedited", "Freight"],
                                   "Air": ["Next Day", "2-Day", "International"],
                                   "Ocean": ["FCL", "LCL", "Refrigerated"]}},
        "rep": {"table": "dim_dispatchers", "id": "dispatcher_id", "id_prefix": "DSP",
                "name_col": "dispatcher_name", "role": "Dispatcher",
                "teams": ["Northeast", "Southeast", "Midwest", "West"]},
    },
    "realestate": {
        "industry": "Real Estate",
        "fact_table": "fact_deals", "fact_record": "deal", "date_col": "listing_date",
        "secondary_date_col": "close_date", "amount_col": "deal_price",
        "statuses": ["Closed", "Active", "Cancelled", "Pending", "Completed"],
        "customer": {"table": "dim_clients", "noun": "client", "id_dim": "client_id",
                     "id_fact": "client_id", "id_prefix": "CLNT",
                     "segments": ["Buyer", "Seller", "Investor", "Guest"],
                     "statuses": ["Active", "Closed", "Prospect", "Repeat"],
                     "adult_required": True},
        "product": {"table": "dim_properties", "noun": "property", "id": "property_id",
                    "id_prefix": "PROP", "name_col": "property_name",
                    "categories": {"Residential": ["Single-Family", "Condo", "Townhome"],
                                   "Commercial": ["Office", "Retail", "Industrial"],
                                   "Land": ["Lot", "Acreage", "Development"]}},
        "rep": {"table": "dim_agents", "id": "agent_id", "id_prefix": "AGT",
                "name_col": "agent_name", "role": "Real Estate Agent",
                "teams": ["Downtown", "Suburban", "Commercial", "Luxury"]},
    },
    "hr": {
        "industry": "HR & Workforce Analytics",
        "fact_table": "fact_timesheets", "fact_record": "timesheet entry", "date_col": "work_date",
        "secondary_date_col": "approved_date", "amount_col": "pay_amount",
        "statuses": ["Approved", "Submitted", "Rejected", "Draft", "Completed"],
        "customer": {"table": "dim_employees", "noun": "employee", "id_dim": "emp_id",
                     "id_fact": "employee_id", "id_prefix": "EMP",
                     "segments": ["Full-Time", "Part-Time", "Contractor", "Guest"],
                     "statuses": ["Active", "Terminated", "On Leave", "Retired"],
                     "adult_required": True},
        "product": {"table": "dim_projects", "noun": "project", "id": "project_id",
                    "id_prefix": "PRJ", "name_col": "project_name",
                    "categories": {"Delivery": ["Client", "Internal", "R&D"],
                                   "Operations": ["Support", "Admin", "Facilities"],
                                   "Growth": ["Sales", "Marketing", "Hiring"]}},
        "rep": {"table": "dim_managers", "id": "manager_id", "id_prefix": "MGR",
                "name_col": "manager_name", "role": "Manager",
                "teams": ["Engineering", "Sales", "Operations", "People"]},
    },
    "edtech": {
        "industry": "EdTech",
        "fact_table": "fact_enrollments", "fact_record": "enrollment", "date_col": "enroll_date",
        "secondary_date_col": "completion_date", "amount_col": "tuition_amount",
        "statuses": ["Completed", "In Progress", "Dropped", "Refunded", "Active"],
        "customer": {"table": "dim_learners", "noun": "learner", "id_dim": "learner_id",
                     "id_fact": "learner_id", "id_prefix": "LRN",
                     "segments": ["Student", "Professional", "Enterprise", "Guest"],
                     "statuses": ["Active", "Churned", "Prospect", "Alumni"],
                     "adult_required": False},
        "product": {"table": "dim_courses", "noun": "course", "id": "course_id",
                    "id_prefix": "CRS", "name_col": "course_name",
                    "categories": {"Data": ["Analytics", "Engineering", "Science"],
                                   "Software": ["Frontend", "Backend", "Mobile"],
                                   "Business": ["Marketing", "Finance", "Leadership"]}},
        "rep": {"table": "dim_instructors", "id": "instructor_id", "id_prefix": "INS",
                "name_col": "instructor_name", "role": "Instructor",
                "teams": ["Data", "Software", "Business", "Design"]},
    },
    "saas": {
        "industry": "SaaS / Subscriptions",
        "fact_table": "fact_subscriptions", "fact_record": "subscription event",
        "date_col": "event_date", "secondary_date_col": "renewal_date",
        "amount_col": "mrr_amount",
        "statuses": ["Active", "Churned", "Trial", "Paused", "Completed"],
        "customer": {"table": "dim_accounts", "noun": "account", "id_dim": "acct_id",
                     "id_fact": "account_id", "id_prefix": "ACCT",
                     "segments": ["SMB", "Mid-Market", "Enterprise", "Guest"],
                     "statuses": ["Active", "Churned", "Trial", "Expansion"],
                     "adult_required": False},
        "product": {"table": "dim_plans", "noun": "plan", "id": "plan_id",
                    "id_prefix": "PLAN", "name_col": "plan_name",
                    "categories": {"Core": ["Starter", "Pro", "Business"],
                                   "Add-On": ["Seats", "Storage", "Support"],
                                   "Platform": ["API", "SSO", "Analytics"]}},
        "rep": {"table": "dim_csms", "id": "csm_id", "id_prefix": "CSM",
                "name_col": "csm_name", "role": "Customer Success Manager",
                "teams": ["SMB", "Mid-Market", "Enterprise", "Onboarding"]},
    },
    "hospitality": {
        "industry": "Hospitality & Travel",
        "fact_table": "fact_bookings", "fact_record": "booking", "date_col": "booking_date",
        "secondary_date_col": "checkout_date", "amount_col": "booking_amount",
        "statuses": ["Completed", "Confirmed", "Cancelled", "No-Show", "Checked-In"],
        "customer": {"table": "dim_guests", "noun": "guest", "id_dim": "guest_id",
                     "id_fact": "guest_id", "id_prefix": "GST",
                     "segments": ["Leisure", "Business", "Group", "Guest"],
                     "statuses": ["Active", "Churned", "Prospect", "Loyalty"],
                     "adult_required": True},
        "product": {"table": "dim_rooms", "noun": "room type", "id": "room_id",
                    "id_prefix": "ROOM", "name_col": "room_name",
                    "categories": {"Standard": ["Queen", "Double", "Single"],
                                   "Premium": ["King", "Suite", "Executive"],
                                   "Specialty": ["Accessible", "Penthouse", "Villa"]}},
        "rep": {"table": "dim_concierges", "id": "concierge_id", "id_prefix": "CNG",
                "name_col": "concierge_name", "role": "Concierge",
                "teams": ["Front Desk", "VIP", "Events", "Travel Desk"]},
    },
}

# Shared geography pool (US). region/state pairs are mostly correct; the
# generator intentionally corrupts a fraction to create mismatched combos.
STATE_REGION = [
    ("CA", "West"), ("WA", "West"), ("OR", "West"), ("NV", "West"), ("AZ", "West"),
    ("TX", "South"), ("FL", "South"), ("GA", "South"), ("NC", "South"), ("VA", "South"),
    ("NY", "Northeast"), ("MA", "Northeast"), ("PA", "Northeast"), ("NJ", "Northeast"),
    ("IL", "Central"), ("OH", "Central"), ("MI", "Central"), ("MN", "Central"), ("MO", "Central"),
]
CITIES = {
    "CA": ["Los Angeles", "San Diego", "San Jose"], "WA": ["Seattle", "Spokane", "Tacoma"],
    "OR": ["Portland", "Eugene", "Salem"], "NV": ["Las Vegas", "Reno", "Henderson"],
    "AZ": ["Phoenix", "Tucson", "Mesa"], "TX": ["Houston", "Dallas", "Austin"],
    "FL": ["Miami", "Orlando", "Tampa"], "GA": ["Atlanta", "Savannah", "Augusta"],
    "NC": ["Charlotte", "Raleigh", "Durham"], "VA": ["Richmond", "Norfolk", "Arlington"],
    "NY": ["New York", "Buffalo", "Rochester"], "MA": ["Boston", "Worcester", "Cambridge"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown"], "NJ": ["Newark", "Jersey City", "Trenton"],
    "IL": ["Chicago", "Aurora", "Naperville"], "OH": ["Columbus", "Cleveland", "Cincinnati"],
    "MI": ["Detroit", "Grand Rapids", "Ann Arbor"], "MN": ["Minneapolis", "St. Paul", "Rochester"],
    "MO": ["St. Louis", "Kansas City", "Springfield"],
}
FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
               "William", "Elizabeth", "David", "Barbara", "Maria", "Jose", "Wei", "Fatima",
               "Aisha", "Chen", "Priya", "Omar", "Sofia", "Liam", "Noah", "Olivia", "Emma"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Lee", "Patel", "Nguyen", "Kim", "Chen"]

START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 6, 30)   # ~30 months of history
TODAY = datetime(2026, 10, 26)     # "now" -- future-dated outliers go beyond this


# --------------------------------------------------------------------------- #
# Messy-formatting helpers
# --------------------------------------------------------------------------- #
def fmt_date_messy(dt, rng):
    """Return a date string in one of three mixed formats (parsing exercise)."""
    style = rng.random()
    if style < 0.34:
        return dt.strftime("%m/%d/%Y")        # 03/14/2024
    elif style < 0.67:
        return dt.strftime("%Y-%m-%d")        # 2024-03-14 (ISO)
    else:
        return dt.strftime("%d-%b-%Y")        # 14-Mar-2024


def fmt_phone_messy(rng):
    a, b, c = rng.randint(200, 989), rng.randint(200, 999), rng.randint(1000, 9999)
    style = rng.random()
    if style < 0.34:
        return "({}) {}-{}".format(a, b, c)
    elif style < 0.67:
        return "{}-{}-{}".format(a, b, c)
    else:
        return "{}{}{}".format(a, b, c)


def fmt_currency_messy(value, rng):
    """Same column, three representations: '$1,200.00' vs '1200' vs '1,200'."""
    style = rng.random()
    if style < 0.34:
        return "${:,.2f}".format(value)
    elif style < 0.67:
        return "{:.0f}".format(value)
    else:
        return "{:,.0f}".format(value)


def fmt_bool_messy(flag, rng):
    """Mixed boolean encodings in a single column."""
    style = rng.random()
    if style < 0.25:
        return "True" if flag else "False"
    elif style < 0.5:
        return "YES" if flag else "NO"
    elif style < 0.75:
        return "1" if flag else "0"
    else:
        return "Y" if flag else "N"


def fmt_id_messy(prefix, n, rng):
    """Inconsistent ID prefixes: 'CUST-001' vs '001' vs 'C001' vs 'CUST001'."""
    style = rng.random()
    if style < 0.4:
        return "{}-{:04d}".format(prefix, n)      # canonical
    elif style < 0.6:
        return "{:04d}".format(n)                 # bare number
    elif style < 0.8:
        return "{}{:04d}".format(prefix[0], n)    # single-letter prefix
    else:
        return "{}{:04d}".format(prefix, n)       # no separator


def messy_case(text, rng):
    """'New York' vs 'new york' vs 'NEW YORK'."""
    style = rng.random()
    if style < 0.6:
        return text
    elif style < 0.8:
        return text.lower()
    else:
        return text.upper()


def messy_name(first, last, rng):
    """Near-duplicate variants: casing, double spaces, trailing space, punctuation."""
    name = "{} {}".format(first, last)
    style = rng.random()
    if style < 0.5:
        return name
    elif style < 0.65:
        return name.lower()
    elif style < 0.8:
        return "{}  {}".format(first, last)       # double space
    elif style < 0.9:
        return name + " "                          # trailing space
    else:
        return "{}. {}".format(first[0], last)     # initial + last


def maybe_null(value, rng, p):
    """Blank out a cell with probability p (randomly null or empty string)."""
    if rng.random() < p:
        return "" if rng.random() < 0.5 else None if False else ""
    return value


def rand_date(rng, start=START_DATE, end=END_DATE):
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, span))


# --------------------------------------------------------------------------- #
# Dimension builders
# --------------------------------------------------------------------------- #
def build_customers(profile, rng, n):
    c = profile["customer"]
    rows = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        state, region = rng.choice(STATE_REGION)
        # Intentional region/state mismatch for ~8% of rows.
        if rng.random() < 0.08:
            _, region = rng.choice(STATE_REGION)
        segment = rng.choice(c["segments"])
        status = rng.choice(c["statuses"])
        # Age: mostly adult, with injected <18 (adult-verification violation)
        # and 999 sentinel outliers.
        r = rng.random()
        if r < 0.02:
            age = 999
        elif r < 0.05:
            age = rng.randint(10, 17)
        else:
            age = rng.randint(18, 85)
        # Structured missingness: Guest segment usually has no email.
        if segment == "Guest":
            email = "" if rng.random() < 0.85 else "{}.{}@example.com".format(first, last).lower()
        else:
            email = "{}.{}@example.com".format(first.lower(), last.lower())
        rows.append({
            c["id_dim"]: fmt_id_messy(c["id_prefix"], i, rng),
            "_raw_id": i,
            "full_name": messy_name(first, last, rng),
            "email": maybe_null(email, rng, 0.05),
            "phone": maybe_null(fmt_phone_messy(rng), rng, 0.10),
            "region": maybe_null(region, rng, 0.04),
            "state": state,
            "segment": segment,
            "join_date": fmt_date_messy(rand_date(rng), rng),
            "status": status,
            "age": age,
        })
    _inject_exact_dupes(rows, rng, 0.04)
    return rows


def build_products(profile, rng, n):
    p = profile["product"]
    cats = p["categories"]
    rows = []
    for i in range(1, n + 1):
        cat = rng.choice(list(cats.keys()))
        sub = rng.choice(cats[cat])
        unit_price = round(rng.uniform(5, 2000), 2)
        cost = round(unit_price * rng.uniform(0.4, 0.85), 2)
        active = rng.random() > 0.2   # ~20% discontinued but still referenced in fact
        launch = rand_date(rng, START_DATE - timedelta(days=720), END_DATE)
        # A few future launch dates (outlier) on inactive items.
        if rng.random() < 0.02:
            launch = TODAY + timedelta(days=rng.randint(30, 400))
        rows.append({
            p["id"]: fmt_id_messy(p["id_prefix"], i, rng),
            "_raw_id": i,
            p["name_col"]: "{} {} {}".format(sub, cat, i),
            "category": messy_case(cat, rng),
            "subcategory": sub,
            "unit_price": maybe_null(fmt_currency_messy(unit_price, rng), rng, 0.05),
            "cost": maybe_null(round(cost, 2), rng, 0.05),
            "active_flag": fmt_bool_messy(active, rng),
            "launch_date": fmt_date_messy(launch, rng),
            "_active": active,
            "_unit_price": unit_price,
        })
    _inject_exact_dupes(rows, rng, 0.03)
    return rows


def build_locations(rng, n):
    rows = []
    for i in range(1, n + 1):
        state, region = rng.choice(STATE_REGION)
        city = rng.choice(CITIES[state])
        # ~10% mismatched region/state combos.
        if rng.random() < 0.10:
            _, region = rng.choice(STATE_REGION)
        rows.append({
            "location_id": fmt_id_messy("LOC", i, rng),
            "_raw_id": i,
            "city": messy_case(city, rng),
            "state": state,
            "region": region,
            "country": rng.choice(["USA", "US", "United States", "U.S.A."]),
            "postal_code": "{:05d}".format(rng.randint(1000, 99999)),
            "territory": "{}-{}".format(region[:1], rng.randint(1, 9)),
        })
    _inject_exact_dupes(rows, rng, 0.03)
    return rows


def build_reps(profile, rng, n):
    r = profile["rep"]
    managers = ["Dana Brooks", "Sam Rivera", "Jordan Patel", "Casey Morgan", "Alex Nguyen"]
    rows = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        rows.append({
            r["id"]: fmt_id_messy(r["id_prefix"], i, rng),
            "_raw_id": i,
            r["name_col"]: "{} {}".format(first, last),
            "team": rng.choice(r["teams"]),
            "manager": rng.choice(managers),
            "hire_date": fmt_date_messy(rand_date(rng, datetime(2018, 1, 1), END_DATE), rng),
            "active": fmt_bool_messy(rng.random() > 0.15, rng),
        })
    return rows


def build_bridge(profile, rng, n_customers, n_reps):
    """Many-to-many: each customer maps to 1-3 reps (two-step join for enrichment)."""
    c = profile["customer"]
    r = profile["rep"]
    rows = []
    for cust in range(1, n_customers + 1):
        for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):   # fanout, skewed to 1
            rows.append({
                c["id_dim"]: fmt_id_messy(c["id_prefix"], cust, rng),
                r["id"]: fmt_id_messy(r["id_prefix"], rng.randint(1, n_reps), rng),
            })
    return rows


def _inject_exact_dupes(rows, rng, pct):
    """Append exact-duplicate rows (identical including ID) for ~pct of the table."""
    k = max(1, int(len(rows) * pct))
    for _ in range(k):
        rows.append(dict(rng.choice(rows)))


# --------------------------------------------------------------------------- #
# CSV writing (dimensions strip private _fields)
# --------------------------------------------------------------------------- #
def write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


# --------------------------------------------------------------------------- #
# Fact table (streamed, so 1M+ rows never sit in memory at once)
# --------------------------------------------------------------------------- #
def write_fact(path, profile, rng, n_rows, n_customers, n_products, n_locations):
    c, p, r = profile["customer"], profile["product"], profile["rep"]
    date_col = profile["date_col"]
    date2_col = profile["secondary_date_col"]
    amount_col = profile["amount_col"]
    statuses = profile["statuses"]
    completed = statuses[0]   # first status is the "closed/completed" state

    header = ["order_id", c["id_fact"], p["id"], "location_id",
              date_col, date2_col, "quantity", "unit_price", amount_col,
              "discount_pct", "status", "order_region", "is_flagged", "satisfaction_score"]

    # Small ring buffer of recent rows so we can re-emit duplicates cheaply.
    recent = []
    written = 0
    oid = 0

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)

        while written < n_rows:
            oid += 1
            # Customer FK: ~4% orphans (id beyond the dimension range).
            if rng.random() < 0.04:
                cust_n = rng.randint(n_customers + 1, n_customers + 300)
            else:
                cust_n = rng.randint(1, n_customers)
            prod_n = rng.randint(1, n_products)
            loc_n = rng.randint(1, n_locations)

            order_dt = rand_date(rng)
            # Secondary date normally after order date...
            ship_dt = order_dt + timedelta(days=rng.randint(1, 30))
            # ...but 3-5 per large run get end-before-start (validation violation).
            if rng.random() < 0.00002:
                ship_dt = order_dt - timedelta(days=rng.randint(1, 10))
            # Future-date outliers (~1%).
            if rng.random() < 0.01:
                order_dt = TODAY + timedelta(days=rng.randint(1, 200))

            qty = rng.randint(1, 20)
            unit_price = round(rng.uniform(5, 2000), 2)
            amount = round(qty * unit_price * rng.uniform(0.9, 1.1), 2)

            status = rng.choice(statuses)

            # Outlier / anomaly injection (2-4% total across several kinds).
            roll = rng.random()
            if roll < 0.01:                         # 10x+ amount spike
                amount = round(amount * rng.uniform(10, 25), 2)
            elif roll < 0.015:                      # negative amount
                amount = -round(rng.uniform(100, 99999), 2)
            elif roll < 0.02:                       # quantity 0 on completed
                qty = 0
                status = completed
            elif roll < 0.023:                      # amount 0 on completed
                amount = 0
                status = completed

            # order_region: usually fine, ~12% independent -> mismatches vs customer dim.
            _, reg = rng.choice(STATE_REGION)
            discount = round(rng.uniform(0, 0.4), 2)
            flagged = rng.random() < 0.08
            score = rng.randint(1, 10)

            row = [
                fmt_id_messy("ORD", oid, rng),
                fmt_id_messy(c["id_prefix"], cust_n, rng),
                fmt_id_messy(p["id_prefix"], prod_n, rng),
                fmt_id_messy("LOC", loc_n, rng),
                maybe_null(fmt_date_messy(order_dt, rng), rng, 0.06),   # some dates blank
                fmt_date_messy(ship_dt, rng),
                maybe_null(qty, rng, 0.03),
                fmt_currency_messy(unit_price, rng),
                maybe_null(fmt_currency_messy(amount, rng) if rng.random() < 0.5 else amount,
                           rng, 0.03),                                   # some measures null
                discount,
                status,
                reg,
                fmt_bool_messy(flagged, rng),
                maybe_null(score, rng, 0.04),
            ]
            w.writerow(row)
            written += 1

            # Keep a small sample of recent rows for duplication.
            if len(recent) < 50:
                recent.append(row)
            elif rng.random() < 0.05:
                recent[rng.randint(0, 49)] = row

            # Duplicate injection (~3% of rows): exact, timestamp-shifted, or
            # same order_id with a different amount (validation trap).
            if written < n_rows and recent and rng.random() < 0.03:
                dup = list(rng.choice(recent))
                kind = rng.random()
                if kind < 0.4:
                    pass                                   # exact duplicate
                elif kind < 0.75:
                    dup[4] = fmt_date_messy(rand_date(rng), rng)   # shifted timestamp
                else:
                    dup[8] = fmt_currency_messy(round(rng.uniform(50, 5000), 2), rng)  # diff amount, same id
                w.writerow(dup)
                written += 1

    return header, written


# --------------------------------------------------------------------------- #
# Wide table for the unpivot exercise (monthly measure, one column per month)
# --------------------------------------------------------------------------- #
def write_wide(path, profile, rng, n_customers):
    c = profile["customer"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header = [c["id_dim"], "year"] + ["{}_target".format(m) for m in months]
    rows = []
    for cust in range(1, min(n_customers, 400) + 1):
        for year in (2023, 2024, 2025):
            vals = [round(rng.uniform(1000, 50000), 2) for _ in months]
            # sprinkle a few nulls
            for j in range(len(vals)):
                if rng.random() < 0.05:
                    vals[j] = ""
            rows.append([fmt_id_messy(c["id_prefix"], cust, rng), year] + vals)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return header


# --------------------------------------------------------------------------- #
# Documentation generators
# --------------------------------------------------------------------------- #
def write_docs(out, profile, counts, fact_header, wide_header):
    c, p, r = profile["customer"], profile["product"], profile["rep"]
    ind = profile["industry"]
    fact = profile["fact_table"]
    rec = profile["fact_record"]

    # --- Entity Relationship Summary ---
    er = """# Entity Relationship Summary -- {ind}

Star schema: one fact table surrounded by dimension and lookup tables.

## Tables
| Table | Grain | Rows (approx) |
|-------|-------|---------------|
| `{fact}` | one row per {rec} | {fact_rows:,} |
| `{cust_tbl}` | one row per {cust_noun} | {cust_rows:,} |
| `{prod_tbl}` | one row per {prod_noun} | {prod_rows:,} |
| `dim_locations` | one row per location | {loc_rows:,} |
| `{rep_tbl}` | one row per {rep_role} | {rep_rows:,} |
| `bridge_{cust_noun}_{rep_noun}` | {cust_noun}-to-{rep_role} link (many-to-many) | {bridge_rows:,} |
| `wide_monthly_targets` | wide format for unpivot practice | {wide_rows:,} |

## Correct join keys
- `{fact}.{cust_fact}`  ->  `{cust_tbl}.{cust_dim}`   (**KEY-NAME MISMATCH on purpose**: fact calls it `{cust_fact}`, the dimension calls it `{cust_dim}`)
- `{fact}.{prod_id}`  ->  `{prod_tbl}.{prod_id}`
- `{fact}.location_id`  ->  `dim_locations.location_id`
- `{cust_tbl}.{cust_dim}`  ->  `bridge_{cust_noun}_{rep_noun}.{cust_dim}`  ->  `{rep_tbl}.{rep_id}`  (**two-step enrichment** to reach the {rep_role})

## Known traps (do NOT treat these as clean data)
1. **Key mismatch** -- the {cust_noun} key is named differently in fact vs dimension (see above).
2. **Orphaned FKs** -- ~4% of `{fact}.{cust_fact}` values have no match in `{cust_tbl}`.
3. **Inconsistent ID formatting** -- IDs appear as `{pfx}-0001`, `0001`, `{pfx0}0001`, `{pfx}0001`. Normalize before joining.
4. **Fanout** -- the bridge maps some {cust_noun}s to multiple {rep_role}s; joining through it inflates measure sums unless you aggregate carefully.
5. **Stale dimensions** -- ~20% of {prod_noun}s are inactive/discontinued and some {cust_noun}s are churned, yet both still appear in recent `{fact}` rows.
""".format(
        ind=ind, fact=fact, rec=rec, fact_rows=counts["fact"],
        cust_tbl=c["table"], cust_noun=c["noun"], cust_rows=counts["customers"],
        prod_tbl=p["table"], prod_noun=p["noun"], prod_rows=counts["products"],
        loc_rows=counts["locations"], rep_tbl=r["table"], rep_role=r["role"],
        rep_noun=r["role"].split()[-1].lower(), rep_rows=counts["reps"],
        bridge_rows=counts["bridge"], wide_rows=counts["wide"],
        cust_fact=c["id_fact"], cust_dim=c["id_dim"], prod_id=p["id"], rep_id=r["id"],
        pfx=c["id_prefix"], pfx0=c["id_prefix"][0],
    )
    with open(os.path.join(out, "ENTITY_RELATIONSHIP_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(er)

    # --- Data Dictionary ---
    dd = ["# Data Dictionary -- {}\n".format(ind),
          "Legend for **Injected issues**: the quality problems deliberately placed in each column.\n"]

    dd.append("\n## `{}`  (fact table)\n".format(fact))
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    fact_desc = {
        "order_id": ("string", "Unique {} identifier".format(rec),
                     "Inconsistent prefixes; some duplicated (exact, timestamp-shifted, or same id w/ different amount)"),
        c["id_fact"]: ("string (FK)", "{} reference".format(c["noun"]),
                       "KEY-NAME MISMATCH vs dim (`{}`); ~4% orphaned; inconsistent prefixes".format(c["id_dim"])),
        p["id"]: ("string (FK)", "{} reference".format(p["noun"]), "Some point to discontinued items"),
        "location_id": ("string (FK)", "Location reference", "Inconsistent prefixes"),
        profile["date_col"]: ("date", "Primary {} date".format(rec),
                              "Mixed formats (MM/DD/YYYY, YYYY-MM-DD, DD-Mon-YYYY); ~6% blank; ~1% future-dated"),
        profile["secondary_date_col"]: ("date", "Follow-up date (ship/close/settle)",
                                        "Mixed formats; a few earlier than the primary date (end < start)"),
        "quantity": ("integer", "Units / count", "~3% null; some 0 on Completed status"),
        "unit_price": ("currency string", "Price per unit", "Mixed currency formats ($1,200.00 / 1200 / 1,200)"),
        profile["amount_col"]: ("currency/number", "{} measure".format(rec.title()),
                                "~3% null; negatives; 10x+ spikes; some 0 on Completed; mixed currency formats"),
        "discount_pct": ("float", "Discount fraction 0-0.4", "-"),
        "status": ("string", "Lifecycle status", "Enables status-based validation rules"),
        "order_region": ("string", "Region recorded on the {}".format(rec),
                         "~12% mismatch the {}'s region in the dimension".format(c["noun"])),
        "is_flagged": ("boolean", "Review/fraud flag", "Mixed encodings (True/False, YES/NO, 1/0, Y/N)"),
        "satisfaction_score": ("integer 1-10", "Experience score", "~4% null"),
    }
    for col in fact_header:
        t, desc, iss = fact_desc.get(col, ("string", "-", "-"))
        dd.append("| `{}` | {} | {} | {} |".format(col, t, desc, iss))

    dd.append("\n## `{}`  ({} dimension)\n".format(c["table"], c["noun"]))
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    for col, t, desc, iss in [
        (c["id_dim"], "string (PK)", "{} id".format(c["noun"]), "Inconsistent prefixes; some IDs referenced in fact are MISSING here (orphans)"),
        ("full_name", "string", "Full name", "Near-duplicates: casing, double spaces, trailing space, initial+last"),
        ("email", "string", "Email address", "Structured missingness: usually blank when segment = Guest; ~5% null elsewhere"),
        ("phone", "string", "Phone", "Mixed formats; ~10% null"),
        ("region", "string", "Region", "~4% null"),
        ("state", "string", "State code", "Some region/state combos mismatched"),
        ("segment", "string", "{} segment/type".format(c["noun"]), "-"),
        ("join_date", "date", "First-seen date", "Mixed formats (cohort anchor)"),
        ("status", "string", "Lifecycle status", "Some marked churned/closed yet active in recent fact rows (stale)"),
        ("age", "integer", "Age", "999 sentinels; some < 18 (adult-verification violations)"),
    ]:
        dd.append("| `{}` | {} | {} | {} |".format(col, t, desc, iss))

    dd.append("\n## `{}`  ({} dimension)\n".format(p["table"], p["noun"]))
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    for col, t, desc, iss in [
        (p["id"], "string (PK)", "{} id".format(p["noun"]), "Inconsistent prefixes; exact duplicates"),
        (p["name_col"], "string", "{} name".format(p["noun"]), "-"),
        ("category", "string", "Category", "Mixed text case (Title / lower / UPPER)"),
        ("subcategory", "string", "Subcategory", "-"),
        ("unit_price", "currency string", "List price", "Mixed currency formats; ~5% null"),
        ("cost", "number", "Unit cost", "~5% null (needed for profit = price - cost)"),
        ("active_flag", "boolean", "Active/discontinued", "Mixed encodings; ~20% inactive yet referenced in fact"),
        ("launch_date", "date", "Launch date", "Mixed formats; a few future-dated"),
    ]:
        dd.append("| `{}` | {} | {} | {} |".format(col, t, desc, iss))

    dd.append("\n## `dim_locations`  (geography)\n")
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    for col, t, desc, iss in [
        ("location_id", "string (PK)", "Location id", "Inconsistent prefixes"),
        ("city", "string", "City", "Mixed text case"),
        ("state", "string", "State code", "-"),
        ("region", "string", "Region", "~10% mismatched vs state"),
        ("country", "string", "Country", "Inconsistent values (USA / US / United States / U.S.A.)"),
        ("postal_code", "string", "ZIP", "-"),
        ("territory", "string", "Sales territory", "-"),
    ]:
        dd.append("| `{}` | {} | {} | {} |".format(col, t, desc, iss))

    dd.append("\n## `{}`  ({} lookup)\n".format(r["table"], r["role"]))
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    for col, t, desc, iss in [
        (r["id"], "string (PK)", "{} id".format(r["role"]), "Inconsistent prefixes"),
        (r["name_col"], "string", "{} name".format(r["role"]), "-"),
        ("team", "string", "Team", "-"),
        ("manager", "string", "Manager", "-"),
        ("hire_date", "date", "Hire date", "Mixed formats"),
        ("active", "boolean", "Active flag", "Mixed encodings"),
    ]:
        dd.append("| `{}` | {} | {} | {} |".format(col, t, desc, iss))

    dd.append("\n## `bridge_{}_{}`  (many-to-many link)\n".format(c["noun"], r["role"].split()[-1].lower()))
    dd.append("| Column | Type | Description | Injected issues |\n|---|---|---|---|")
    dd.append("| `{}` | string (FK) | {} id | Links to {} |".format(c["id_dim"], c["noun"], c["table"]))
    dd.append("| `{}` | string (FK) | {} id | Links to {}; fanout (1-3 per {}) |".format(r["id"], r["role"], r["table"], c["noun"]))

    dd.append("\n## `wide_monthly_targets`  (wide format -- unpivot me)\n")
    dd.append("One row per {}-year; twelve `<Mon>_target` columns. Unpivot to long format (one row per {}-month) before analysis.\n".format(c["noun"], c["noun"]))

    with open(os.path.join(out, "DATA_DICTIONARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(dd) + "\n")

    # --- Analyst Exercises ---
    ex = """# Analyst Exercise List -- {ind}

Ten tasks to complete **before** building a dashboard. They move through the full
workflow: profile -> clean -> join -> transform -> validate -> aggregate. File names
below refer to the CSVs in this folder.

## 1. Profile & assess quality
Load every table. For each, report row count, null rate per column, and spot the
columns with mixed formats. Expect ~10-15% missing values overall.

## 2. Standardize IDs, then join fact to {cust_noun}
Normalize the inconsistent ID prefixes (`{pfx}-0001` / `0001` / `{pfx0}0001` / `{pfx}0001`)
to one canonical form. Join `{fact}.{cust_fact}` to `{cust_tbl}.{cust_dim}`
(**note the different key names**). Count how many fact rows have no matching
{cust_noun} (orphans) -- you should find ~4%.

## 3. Parse the mixed date formats
`{date_col}` mixes MM/DD/YYYY, YYYY-MM-DD, and DD-Mon-YYYY in one column. Parse all
three into real dates. Flag the blanks and the future-dated rows separately.

## 4. De-duplicate
Find exact duplicate rows and near-duplicates (names differing only by case,
spacing, or punctuation in `{cust_tbl}`). In `{fact}`, find the same {rec} recorded
twice with a shifted timestamp, and the same `order_id` carrying two different
amounts. Decide a dedupe rule and document it.

## 5. Clean the measures
`unit_price` and `{amount_col}` mix currency formats ($1,200.00 / 1200 / 1,200).
Strip them to numbers. Then quarantine the anomalies: negative amounts, 10x+ spikes
(above the 99th percentile), quantity = 0 on Completed {rec}s, and amount = 0 on
Completed {rec}s.

## 6. Build calculated columns
After joining `{prod_tbl}` for `cost`: compute `profit = {amount_col} - cost`.
Compute `days_to_close = {date2_col} - {date_col}`. Extract `year`, `month`,
`quarter`, and `weekday` from `{date_col}`.

## 7. Bin and bucket
Create `age_group` from the {cust_noun} age (handle the 999 sentinels and <18 cases
first), a `revenue_tier` from `{amount_col}`, and a `quantity_bucket`.

## 8. Two-step enrichment via the bridge (watch for fanout)
Attach the {rep_role} to each {rec} by joining through `bridge_{cust_noun}_{rep_noun}`.
Because some {cust_noun}s map to multiple {rep_role}s, a naive join inflates
`{amount_col}` sums -- show the inflated total vs the correct total and explain the gap.

## 9. Validate business rules
Produce an exceptions report for: (a) `{date2_col}` earlier than `{date_col}`,
(b) amount = 0 on Completed status, (c) {cust_noun} age < 18 where adult verification
is required, (d) duplicate `order_id`s with different amounts, and (e) `order_region`
in `{fact}` disagreeing with the {cust_noun}'s region in `{cust_tbl}`.

## 10. Unpivot, then aggregate for the dashboard
Unpivot `wide_monthly_targets` to long format. Then build the dashboard-ready
aggregates: a 24-month time-series trend, a 7-day and 30-day rolling average, a
cohort-retention grid from `join_date` + first {rec} date, and an RFM table
(recency, frequency, monetary) per {cust_noun}. These feed the time series, KPI
cards, geographic heatmap, scatter/correlation, cohort, and ranking charts.
""".format(
        ind=ind, fact=fact, rec=rec, cust_noun=c["noun"], cust_tbl=c["table"],
        cust_fact=c["id_fact"], cust_dim=c["id_dim"], prod_tbl=p["table"],
        rep_role=r["role"], rep_noun=r["role"].split()[-1].lower(),
        date_col=profile["date_col"], date2_col=profile["secondary_date_col"],
        amount_col=profile["amount_col"], pfx=c["id_prefix"], pfx0=c["id_prefix"][0],
    )
    with open(os.path.join(out, "ANALYST_EXERCISES.md"), "w", encoding="utf-8") as f:
        f.write(ex)


# --------------------------------------------------------------------------- #
# Profile resolution
# --------------------------------------------------------------------------- #
def resolve_profile(args):
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            return json.load(f)
    if not args.industry:
        sys.exit("Provide --industry (matching a preset) or --config path.json. Use --list to see presets.")
    key = args.industry.lower()
    # direct key match
    if key in PRESETS:
        return PRESETS[key]
    # fuzzy: match on substring of the preset's display name or key
    for k, prof in PRESETS.items():
        name = prof["industry"].lower()
        if key in name or name in key or key in k or k in key:
            return prof
    # token overlap fallback
    toks = set(key.replace("&", " ").replace("/", " ").split())
    best, best_score = None, 0
    for k, prof in PRESETS.items():
        ptoks = set(prof["industry"].lower().replace("&", " ").replace("/", " ").split())
        score = len(toks & ptoks)
        if score > best_score:
            best, best_score = prof, score
    if best and best_score > 0:
        return best
    sys.exit(
        "No preset matched '{}'. For a novel industry, create a --config JSON "
        "(see references/industry-profiles.md) and pass it with --config.".format(args.industry)
    )


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Generate a messy multi-table analyst dataset.")
    ap.add_argument("--industry", help="Industry name (matched against built-in presets).")
    ap.add_argument("--config", help="Path to a custom industry-profile JSON (for industries not in presets).")
    ap.add_argument("--rows", type=int, default=1_000_000, help="Fact-table row count (default 1,000,000).")
    ap.add_argument("--out", default="./output", help="Output directory.")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (deterministic output).")
    ap.add_argument("--customers", type=int, default=1000, help="Dimension size: 800-1200 recommended.")
    ap.add_argument("--products", type=int, default=200, help="Dimension size: 150-300 recommended.")
    ap.add_argument("--locations", type=int, default=100, help="Dimension size: 80-120 recommended.")
    ap.add_argument("--reps", type=int, default=75, help="Lookup size: 50-100 recommended.")
    ap.add_argument("--list", action="store_true", help="List built-in industry presets and exit.")
    args = ap.parse_args()

    if args.list:
        print("Built-in industry presets (pass --industry with any of these names):\n")
        for k, prof in PRESETS.items():
            print("  {:16s} {}".format(k, prof["industry"]))
        print("\nAny other industry: supply a --config JSON (see references/industry-profiles.md).")
        return

    profile = resolve_profile(args)
    rng = random.Random(args.seed)
    out = args.out
    os.makedirs(out, exist_ok=True)

    c, p, r = profile["customer"], profile["product"], profile["rep"]
    print("Industry : {}".format(profile["industry"]))
    print("Output   : {}".format(os.path.abspath(out)))
    print("Fact rows: {:,} (target)".format(args.rows))

    # Dimensions
    print("Building dimensions...")
    customers = build_customers(profile, rng, args.customers)
    products = build_products(profile, rng, args.products)
    locations = build_locations(rng, args.locations)
    reps = build_reps(profile, rng, args.reps)
    bridge = build_bridge(profile, rng, args.customers, args.reps)

    cust_header = [c["id_dim"], "full_name", "email", "phone", "region", "state",
                   "segment", "join_date", "status", "age"]
    prod_header = [p["id"], p["name_col"], "category", "subcategory", "unit_price",
                   "cost", "active_flag", "launch_date"]
    loc_header = ["location_id", "city", "state", "region", "country", "postal_code", "territory"]
    rep_header = [r["id"], r["name_col"], "team", "manager", "hire_date", "active"]
    bridge_header = [c["id_dim"], r["id"]]

    write_csv(os.path.join(out, c["table"] + ".csv"), customers, cust_header)
    write_csv(os.path.join(out, p["table"] + ".csv"), products, prod_header)
    write_csv(os.path.join(out, "dim_locations.csv"), locations, loc_header)
    write_csv(os.path.join(out, r["table"] + ".csv"), reps, rep_header)
    bridge_name = "bridge_{}_{}".format(c["noun"], r["role"].split()[-1].lower())
    write_csv(os.path.join(out, bridge_name + ".csv"), bridge, bridge_header)

    # Wide table
    wide_header = write_wide(os.path.join(out, "wide_monthly_targets.csv"), profile, rng, args.customers)

    # Fact (streamed)
    print("Streaming fact table ({:,} rows target)...".format(args.rows))
    fact_header, fact_written = write_fact(
        os.path.join(out, profile["fact_table"] + ".csv"),
        profile, rng, args.rows, args.customers, args.products, args.locations)

    counts = {
        "fact": fact_written,
        "customers": len(customers), "products": len(products),
        "locations": len(locations), "reps": len(reps),
        "bridge": len(bridge), "wide": (min(args.customers, 400) * 3),
    }

    print("Writing documentation (ER summary, data dictionary, exercises)...")
    write_docs(out, profile, counts, fact_header, wide_header)

    print("\nDone. Files written to {}:".format(os.path.abspath(out)))
    for fn in sorted(os.listdir(out)):
        path = os.path.join(out, fn)
        size = os.path.getsize(path)
        human = "{:.1f} MB".format(size / 1e6) if size > 1e6 else "{:.0f} KB".format(size / 1e3)
        print("  {:42s} {}".format(fn, human))
    print("\nFact rows actually written (incl. injected duplicates): {:,}".format(fact_written))


if __name__ == "__main__":
    main()
