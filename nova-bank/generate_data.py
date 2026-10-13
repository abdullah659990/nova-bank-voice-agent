#!/usr/bin/env python3
"""
Nova Bank fake data generator. ALL DATA IS FAKE.

Creates realistic customers, accounts, cards, transactions, loans,
transfers and past tickets, loads them into Postgres, and writes
test_customers.md: a cheat sheet of customers to use for each test scenario.

Usage:
  python generate_data.py          # load into Postgres
  python generate_data.py --csv    # dry run: write CSV files instead
"""
import csv
import random
import re
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from faker import Faker

# ---------------- settings ----------------
DB = dict(host="localhost", port=5432, dbname="novabank",
          user="bank", password="bankpass")
N_CUSTOMERS = 500
HISTORY_DAYS = 180
SEED = 42
HERE = Path(__file__).parent

random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
TODAY = date.today()
NOW = datetime.now().replace(microsecond=0)

SECURITY_QUESTIONS = {
    "What is your favorite fruit?": ["mango", "apple", "banana", "orange", "grape", "peach", "cherry", "lemon"],
    "What was the name of your first pet?": ["max", "bella", "charlie", "luna", "rocky", "daisy", "milo", "coco"],
    "What is your favorite color?": ["blue", "green", "red", "purple", "yellow", "black", "white", "pink"],
    "In what city were you born?": ["boston", "denver", "austin", "seattle", "miami", "chicago", "phoenix", "dallas"],
}

# (category, merchants, min amount, max amount, weight)
SPEND = [
    ("groceries", ["Whole Foods", "Trader Joe's", "Kroger", "Safeway", "Costco"], 15, 220, 18),
    ("dining", ["Starbucks", "Chipotle", "McDonald's", "Olive Garden", "Corner Diner"], 4, 90, 16),
    ("fuel", ["Shell", "Chevron", "Exxon", "BP"], 25, 80, 8),
    ("shopping", ["Amazon", "Target", "Walmart", "Best Buy", "Nike"], 10, 400, 12),
    ("transport", ["Uber", "Lyft", "Metro Transit"], 3, 60, 6),
    ("entertainment", ["AMC Theatres", "Steam", "Ticketmaster"], 8, 120, 4),
    ("health", ["CVS Pharmacy", "Walgreens", "City Dental"], 8, 250, 3),
    ("travel", ["Delta Air Lines", "Marriott", "Airbnb", "Expedia"], 80, 1200, 2),
]
SUBSCRIPTIONS = [("Netflix", 15.49), ("Spotify", 11.99), ("Amazon Prime", 14.99),
                 ("Planet Fitness", 24.99), ("iCloud Storage", 2.99), ("Hulu", 17.99)]
SUSPICIOUS = ["ONLINE PURCHASE - GLOBALTECH TRADING HK", "INTL POS - ELECTRO MART LAGOS NG",
              "CRYPTO EXCHANGE - BITXPRESS LTD", "ONLINE PURCHASE - LUXE WATCHES RU"]
DOMESTIC_BANKS = ["Chase", "Bank of America", "Wells Fargo", "Citibank", "US Bank"]
INTL_BANKS = ["HSBC (United Kingdom)", "Deutsche Bank (Germany)", "Meezan Bank (Pakistan)",
              "Emirates NBD (UAE)", "BNP Paribas (France)", "ICICI Bank (India)"]
FAILURE_REASONS = ["Incorrect beneficiary account number", "Beneficiary bank rejected the payment",
                   "Beneficiary name does not match account"]
TICKET_TEMPLATES = [
    ("card", "Card declined at a store even though the balance was sufficient."),
    ("card", "Requested a replacement card that has not arrived yet."),
    ("account", "Asked why a monthly account fee was charged."),
    ("transfer", "International transfer is taking longer than expected."),
    ("loan", "Wants to know how to pay off the loan early."),
    ("online banking", "Cannot log in to the mobile app after changing phones."),
    ("fees", "Charged an overdraft fee and wants it reviewed."),
]


# ---------------- helpers ----------------
def money(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rand_money(a, b):
    return money(random.uniform(a, b))


def digits(n):
    return "".join(random.choice("0123456789") for _ in range(n))


def phone():
    return "+1" + random.choice("23456789") + digits(9)


def pick(options, weights):
    return random.choices(options, weights)[0]


def at(d, h1=7, h2=22):
    t = datetime.combine(d, datetime.min.time()) + timedelta(
        hours=random.randint(h1, h2), minutes=random.randint(0, 59))
    return min(t, NOW - timedelta(minutes=5))


class Ids:
    def __init__(self):
        self.counters = {}

    def next(self, prefix, start):
        self.counters[prefix] = self.counters.get(prefix, start) + 1
        return f"{prefix}{self.counters[prefix]}"


def loan_payment(p, rate, n):
    r = rate / 100 / 12
    return p * r / (1 - (1 + r) ** -n)


def loan_remaining(p, rate, n, k):
    r = rate / 100 / 12
    pay = loan_payment(p, rate, n)
    return p * (1 + r) ** k - pay * (((1 + r) ** k - 1) / r)


# ---------------- generation ----------------
ids = Ids()
T = {name: [] for name in
     ["customers", "accounts", "cards", "transactions", "loans", "transfers", "tickets"]}
scenarios = {}  # scenario name -> list of customer ids


def mark(scenario, cid):
    scenarios.setdefault(scenario, [])
    if cid not in scenarios[scenario]:
        scenarios[scenario].append(cid)


def ev(time, desc, cat, amount, channel, flexible=False):
    return dict(time=time, desc=desc, cat=cat, amount=money(amount),
                channel=channel, flexible=flexible)


for i in range(N_CUSTOMERS):
    cid = str(10001 + i)
    first, last = fake.first_name(), fake.last_name()
    question = random.choice(list(SECURITY_QUESTIONS))
    answer = random.choice(SECURITY_QUESTIONS[question])
    since = TODAY - timedelta(days=random.randint(400, 3650))
    kyc = pick(["verified", "pending", "expired"], [94, 4, 2])
    email = re.sub(r"[^a-z0-9.@]", "", f"{first}.{last}{random.randint(1, 99)}@example.com".lower())
    T["customers"].append((cid, f"{first} {last}", fake.date_of_birth(minimum_age=19, maximum_age=80),
                           phone(), email, fake.street_address(), fake.city(), fake.state_abbr(),
                           question, answer, kyc, since))
    if kyc != "verified":
        mark(f"kyc_{kyc}", cid)

    # spending profile
    salary = random.randrange(2500, 9001, 50)
    scale = max(0.6, min(1.6, salary / 5000))
    payday = random.choice([1, 15])
    rent = money(salary * random.uniform(0.25, 0.38))
    employer = fake.company()
    subs = random.sample(SUBSCRIPTIONS, random.randint(1, 4))
    start = TODAY - timedelta(days=HISTORY_DAYS)

    # ---- checking account ----
    chk = ids.next("A", 50000)
    status, reason = pick([("active", None),
                           ("frozen", "Temporary hold for suspected fraud review"),
                           ("dormant", "No customer activity for over 12 months")], [95, 3, 2])
    overdraft = money(random.choice([0, 250, 500]))
    opened = since + timedelta(days=random.randint(0, 30))
    events = []
    activity_cutoff = TODAY - timedelta(days=150) if status == "dormant" else TODAY
    if status != "active":
        mark(f"account_{status}", cid)

    # ---- loan (decided first, its payments show up in checking) ----
    if random.random() < 0.35:
        ltype = pick(["personal", "auto", "home"], [50, 35, 15])
        p_rng, r_rng, terms = {"personal": ((5000, 40000), (8, 18), [24, 36, 48, 60]),
                               "auto": ((10000, 50000), (4, 9), [36, 48, 60, 72]),
                               "home": ((150000, 600000), (3, 7), [180, 240, 360])}[ltype]
        principal = money(random.randrange(*p_rng, 500))
        rate = round(random.uniform(*r_rng), 2)
        term = random.choice(terms)
        paid = random.randint(2, term - 1)
        pay = money(loan_payment(float(principal), rate, term))
        lstatus = pick(["current", "late", "paid_off"], [86, 10, 4])
        remaining = money(loan_remaining(float(principal), rate, term, paid))
        dpd, next_due = 0, TODAY + timedelta(days=random.randint(1, 28))
        if lstatus == "late":
            dpd = random.randint(5, 75)
            next_due = TODAY - timedelta(days=dpd)
            mark("loan_late", cid)
        elif lstatus == "paid_off":
            remaining, next_due = money(0), None
        T["loans"].append((ids.next("L", 70000), cid, ltype, principal, rate, term, pay, remaining,
                           TODAY - timedelta(days=30 * paid), next_due, lstatus, dpd))
        loan_payments = lstatus == "current"
        if ltype == "home":
            rent = money(0)
    else:
        pay, loan_payments = None, False

    # ---- savings account ----
    has_savings = random.random() < 0.6
    if has_savings:
        sav = ids.next("A", 50000)
        sav_rate = money(random.choice([0.5, 1.0, 2.5, 4.0]))
        sav_balance = rand_money(500, 25000)
        sav_events = []

    # ---- regular monthly activity ----
    d = start
    while d <= activity_cutoff:
        if d.day == payday:
            events.append(ev(at(d, 5, 7), f"Payroll deposit - {employer}", "income",
                             salary * random.uniform(0.98, 1.02), "direct_deposit"))
        if d.day == 3 and rent:
            events.append(ev(at(d), "Rent payment - Oakview Properties", "housing", -rent, "direct_debit"))
        if d.day == 10:
            events.append(ev(at(d), "City Power & Electric", "utilities", -rand_money(60, 180), "direct_debit"))
        if d.day == 12:
            events.append(ev(at(d), "Comcast Xfinity Internet", "utilities", -rand_money(50, 90), "direct_debit"))
        if d.day == 18:
            events.append(ev(at(d), "Verizon Wireless", "utilities", -rand_money(40, 110), "direct_debit"))
        if d.day == 20 and loan_payments:
            events.append(ev(at(d), "Nova Bank loan payment", "loan", -pay, "direct_debit"))
        for k, (name, price) in enumerate(subs):
            if d.day == 5 + k * 4:
                events.append(ev(at(d), name, "subscriptions", -price, "card"))
        if has_savings and d.day == 2:
            amt = rand_money(100, 800)
            t = at(d)
            events.append(ev(t, "Transfer to Savings", "transfer", -amt, "transfer"))
            sav_events.append(ev(t, "Transfer from Checking", "transfer", amt, "transfer"))
        if has_savings and d.day == 28:
            sav_events.append(ev(at(d, 3, 4), "Interest payment", "interest", 0, "interest"))
        for _ in range(pick([0, 1, 2, 3], [30, 40, 20, 10])):
            cat, merchants, lo, hi, _w = random.choices(SPEND, [s[4] for s in SPEND])[0]
            events.append(ev(at(d), random.choice(merchants), cat,
                             -rand_money(lo, hi) * Decimal(str(scale)), "card", flexible=True))
        if random.random() < 0.04:
            events.append(ev(at(d), "ATM withdrawal", "cash", -random.randrange(20, 301, 20), "atm", True))
        d += timedelta(days=1)

    # ---- special scenarios ----
    recent_card = [e for e in events if e["channel"] == "card" and e["flexible"]
                   and e["time"] > NOW - timedelta(days=30)]
    if status == "active" and recent_card and random.random() < 0.06:
        dup = dict(random.choice(recent_card))
        dup["time"] = dup["time"] + timedelta(minutes=2)
        dup["flexible"] = False
        events.append(dup)
        mark("duplicate_charge", cid)
    if status == "active" and random.random() < 0.03:
        for _ in range(random.randint(2, 3)):
            events.append(ev(at(TODAY - timedelta(days=random.randint(0, 3)), 0, 23),
                             random.choice(SUSPICIOUS), "shopping", -rand_money(250, 950), "card"))
        mark("suspicious_activity", cid)

    # ---- transfers ----
    if status == "active" and random.random() < 0.4:
        for _ in range(random.randint(1, 4)):
            intl = random.random() < 0.3
            amount = rand_money(100, min(5000, salary * 0.6)) if intl else rand_money(50, min(3000, salary * 0.5))
            fee = money(25 if intl else 0)
            initiated = at(TODAY - timedelta(days=random.randint(0, 30)))
            expected = initiated.date() + timedelta(days=random.randint(3, 5) if intl else 1)
            failure = None
            if expected >= TODAY:
                tstatus = "processing"
            else:
                opts = ["completed", "failed", "returned"] + (["compliance_hold"] if intl else [])
                tstatus = pick(opts, [85, 8, 4] + ([3] if intl else []))
            if tstatus in ("failed", "returned"):
                failure = random.choice(FAILURE_REASONS)
            if tstatus == "compliance_hold":
                failure = "Held for routine compliance review; documents may be requested"
            name = fake.name()
            bank = random.choice(INTL_BANKS if intl else DOMESTIC_BANKS)
            T["transfers"].append((ids.next("X", 90000), chk, "international" if intl else "domestic",
                                   name, bank, amount, fee, initiated, expected, tstatus, failure))
            events.append(ev(initiated, f"Transfer to {name} - {bank}", "transfer", -amount, "transfer"))
            if fee:
                events.append(ev(initiated, "International transfer fee", "fees", -fee, "fee"))
            if tstatus in ("failed", "returned"):
                events.append(ev(initiated + timedelta(days=2), f"Returned transfer - {name}",
                                 "transfer", amount, "transfer"))
            if tstatus != "completed":
                mark(f"transfer_{tstatus}" + ("_international" if intl else ""), cid)

    # ---- apply balances ----
    # Pick a starting balance so the account never drops below zero,
    # except for a few customers who dip into their overdraft.
    events.sort(key=lambda e: e["time"])
    running, lowest = money(0), money(0)
    for e in events:
        running += e["amount"]
        lowest = min(lowest, running)
    if overdraft > 0 and status == "active" and random.random() < 0.08:
        balance = -lowest - overdraft * Decimal("0.6")
    else:
        balance = -lowest + rand_money(150, 3000)
    for e in events:
        balance += e["amount"]
        recent = e["time"] > NOW - timedelta(days=2)
        tstatus = "pending" if recent and e["channel"] == "card" and random.random() < 0.5 else "posted"
        T["transactions"].append((ids.next("T", 1000000), chk, e["time"], e["desc"], e["cat"],
                                  e["amount"], e["channel"], tstatus))
    if balance < 0:
        mark("overdrawn_account", cid)
    T["accounts"].append((chk, cid, "checking", digits(4), money(balance), "USD", status, reason,
                          overdraft, money(0), opened))
    if has_savings:
        bal = sav_balance
        for e in sorted(sav_events, key=lambda e: e["time"]):
            if e["channel"] == "interest":
                e["amount"] = money(bal * sav_rate / 100 / 12)
            bal += e["amount"]
            T["transactions"].append((ids.next("T", 1000000), sav, e["time"], e["desc"], e["cat"],
                                      e["amount"], e["channel"], "posted"))
        T["accounts"].append((sav, cid, "savings", digits(4), money(bal), "USD", "active", None,
                              money(0), sav_rate, opened + timedelta(days=random.randint(0, 300))))

    # ---- cards ----
    cstatus = pick(["active", "blocked", "lost", "expired"], [91, 3, 3, 3])
    expiry = (TODAY - timedelta(days=random.randint(10, 200)) if cstatus == "expired"
              else TODAY + timedelta(days=random.randint(120, 1400)))
    T["cards"].append((ids.next("K", 30000), cid, chk, "debit", digits(4), cstatus, expiry,
                       money(random.choice([500, 1000, 2000, 5000])), None, None, None, None))
    if cstatus != "active":
        mark(f"debit_card_{cstatus}", cid)
    if random.random() < 0.5:
        limit = money(random.randrange(1000, 15001, 500))
        outstanding = money(float(limit) * random.uniform(0, 0.95))
        minimum = money(max(25, float(outstanding) * 0.03)) if outstanding > 0 else money(0)
        T["cards"].append((ids.next("K", 30000), cid, None, "credit", digits(4), "active",
                           TODAY + timedelta(days=random.randint(120, 1400)), None, limit,
                           outstanding, minimum, TODAY + timedelta(days=random.randint(1, 25))))
        if outstanding > limit * Decimal("0.85"):
            mark("credit_card_near_limit", cid)

    # ---- past tickets ----
    if random.random() < 0.1:
        cat, desc = random.choice(TICKET_TEMPLATES)
        tstatus = pick(["open", "in_progress", "resolved"], [30, 20, 50])
        resolution = "Issue resolved by support team." if tstatus == "resolved" else None
        T["tickets"].append((cid, cat, "normal", desc, tstatus,
                             NOW - timedelta(days=random.randint(2, 120)), resolution))
        if tstatus != "resolved":
            mark("open_ticket", cid)

    if not any(cid in lst for lst in scenarios.values()):
        mark("normal_customer", cid)


# ---------------- output ----------------
COLUMNS = {
    "customers": "customer_id, full_name, date_of_birth, phone, email, address, city, state, "
                 "security_question, security_answer, kyc_status, customer_since",
    "accounts": "account_id, customer_id, account_type, last4, balance, currency, status, "
                "status_reason, overdraft_limit, interest_rate, opened_on",
    "cards": "card_id, customer_id, account_id, card_type, last4, status, expiry, daily_limit, "
             "credit_limit, outstanding, minimum_payment, payment_due",
    "transactions": "txn_id, account_id, txn_time, description, category, amount, channel, status",
    "loans": "loan_id, customer_id, loan_type, principal, interest_rate, term_months, "
             "monthly_payment, remaining_balance, start_date, next_due_date, status, days_past_due",
    "transfers": "transfer_id, from_account_id, transfer_type, beneficiary_name, beneficiary_bank, "
                 "amount, fee, initiated_at, expected_completion, status, failure_reason",
    "tickets": "customer_id, category, priority, description, status, created_at, resolution",
}
ORDER = ["customers", "accounts", "cards", "transactions", "loans", "transfers", "tickets"]


def write_csv():
    out = HERE / "csv"
    out.mkdir(exist_ok=True)
    for name in ORDER:
        with open(out / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([c.strip() for c in COLUMNS[name].split(",")])
            w.writerows(T[name])
    print(f"CSV files written to {out}")


def load_postgres():
    import psycopg
    with psycopg.connect(**DB) as conn:
        with conn.cursor() as cur:
            cur.execute((HERE / "schema.sql").read_text())
            for name in ORDER:
                with cur.copy(f"COPY {name} ({COLUMNS[name]}) FROM STDIN") as cp:
                    for row in T[name]:
                        cp.write_row(row)
        conn.commit()
    print("Loaded into Postgres database 'novabank'.")


def write_cheat_sheet():
    by_id = {c[0]: c for c in T["customers"]}
    lines = ["# Nova Bank test customers (ALL FAKE)", "",
             "Use these to test each scenario on a call. Columns: ID, name, security question, answer.", ""]
    for scenario in sorted(scenarios):
        lines.append(f"## {scenario.replace('_', ' ')} ({len(scenarios[scenario])} customers)")
        for cid in scenarios[scenario][:3]:
            c = by_id[cid]
            lines.append(f"- **{cid}**, {c[1]}. \"{c[8]}\" -> `{c[9]}`")
        lines.append("")
    (HERE / "test_customers.md").write_text("\n".join(lines))
    print(f"Cheat sheet written to {HERE / 'test_customers.md'}")


if __name__ == "__main__":
    for name in ORDER:
        print(f"{name:13} {len(T[name]):>7} rows")
    if "--csv" in sys.argv:
        write_csv()
    else:
        load_postgres()
    write_cheat_sheet()
