"""
Seeds the SubscriptionPulse PostgreSQL database with baseline test data.

Creates accounts, usage events, invoices, and subscription history while
maintaining relationships and basic data integrity constraints. Activity
volume and invoice amounts vary by subscription tier.

Run after the PostgreSQL container is initialized.
"""

import random
from datetime import datetime, timedelta

import psycopg2
from faker import Faker

fake = Faker()

# PostgreSQL connection settings matching docker-compose.yml.
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,  # matches the host port in docker-compose.yml (5433:5432)
    "dbname": "subscriptionpulse",
    "user": "postgres",
    "password": "postgres",
}

NUM_ACCOUNTS = 100

# Usage volume ranges by subscription tier.
EVENT_VOLUME_BY_TIER = {
    "starter": (5, 15),
    "pro": (15, 40),
    "enterprise": (40, 80),
}

# Base monthly price by subscription tier.
MONTHLY_PRICE_BY_TIER = {
    "starter": 9.00,
    "pro": 29.00,
    "enterprise": 99.00,
}

EVENT_TYPES = [
    "login",
    "task_created",
    "task_completed",
    "comment_added",
    "teammate_invited",
    "board_created",
]

PLAN_TIERS = ["starter", "pro", "enterprise"]
PLAN_WEIGHTS = [0.50, 0.35, 0.15]  # distribution weighted toward starter plans

STATUSES = ["active", "paused", "churned"]
STATUS_WEIGHTS = [0.85, 0.10, 0.05]

INVOICE_STATUSES = ["paid", "failed", "refunded"]
INVOICE_STATUS_WEIGHTS = [0.90, 0.07, 0.03]

PAYMENT_METHODS = ["credit_card", "paypal", "bank_transfer"]


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def seed_accounts(conn, n=NUM_ACCOUNTS):
    """Create accounts and return IDs, plan tiers, and signup dates."""
    rows = []
    for _ in range(n):
        workspace_name = fake.company()
        contact_email = fake.unique.company_email()
        signup_date = fake.date_between(start_date="-2y", end_date="-30d")
        plan_tier = random.choices(PLAN_TIERS, weights=PLAN_WEIGHTS)[0]
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        rows.append((workspace_name, contact_email, signup_date, plan_tier, status))

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO accounts (workspace_name, contact_email, signup_date, plan_tier, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING account_id
            """,
            rows,
        )
    conn.commit()

    # Retrieve generated account IDs for dependent seed records.
    with conn.cursor() as cur:
        cur.execute("SELECT account_id, plan_tier, signup_date FROM accounts")
        accounts = cur.fetchall()
    print(f"Seeded {len(accounts)} accounts.")
    return accounts


def seed_signup_changes(conn, accounts):
    """Record each account's initial subscription state."""
    rows = [
        (account_id, None, plan_tier, signup_date)
        for account_id, plan_tier, signup_date in accounts
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO subscription_changes (account_id, old_plan, new_plan, change_date)
            VALUES (%s, %s, %s, %s)
            """,
            rows,
        )
    conn.commit()
    print(f"Seeded {len(rows)} signup rows in subscription_changes.")


def seed_usage_events(conn, accounts):
    """Generate tier-based usage activity between signup and the current date."""
    rows = []
    now = datetime.now()
    for account_id, plan_tier, signup_date in accounts:
        low, high = EVENT_VOLUME_BY_TIER[plan_tier]
        num_events = random.randint(low, high)
        signup_dt = datetime.combine(signup_date, datetime.min.time())

        for _ in range(num_events):
            event_time = fake.date_time_between(start_date=signup_dt, end_date=now)
            event_type = random.choice(EVENT_TYPES)
            rows.append((account_id, event_type, event_time))

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO usage_events (account_id, event_type, event_time)
            VALUES (%s, %s, %s)
            """,
            rows,
        )
    conn.commit()
    print(f"Seeded {len(rows)} usage_events rows.")


def seed_invoices(conn, accounts):
    """Generate monthly invoices using tier-based pricing."""
    rows = []
    today = datetime.now().date()

    for account_id, plan_tier, signup_date in accounts:
        base_price = MONTHLY_PRICE_BY_TIER[plan_tier]
        invoice_date = signup_date
        while invoice_date <= today:
            amount = round(base_price * random.uniform(0.95, 1.05), 2)
            status = random.choices(INVOICE_STATUSES, weights=INVOICE_STATUS_WEIGHTS)[0]
            payment_method = random.choice(PAYMENT_METHODS)
            rows.append((account_id, amount, invoice_date, payment_method, status))
            invoice_date += timedelta(days=30)

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO invoices (account_id, amount, invoice_date, payment_method, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            rows,
        )
    conn.commit()
    print(f"Seeded {len(rows)} invoices.")


def verify_referential_integrity(conn):
    """Check dependent tables for account IDs missing from the accounts table."""
    checks = {
        "usage_events": "SELECT COUNT(*) FROM usage_events e LEFT JOIN accounts a ON e.account_id = a.account_id WHERE a.account_id IS NULL",
        "invoices": "SELECT COUNT(*) FROM invoices i LEFT JOIN accounts a ON i.account_id = a.account_id WHERE a.account_id IS NULL",
        "subscription_changes": "SELECT COUNT(*) FROM subscription_changes s LEFT JOIN accounts a ON s.account_id = a.account_id WHERE a.account_id IS NULL",
    }
    with conn.cursor() as cur:
        for table, query in checks.items():
            cur.execute(query)
            orphan_count = cur.fetchone()[0]
            print(f"Orphan rows in {table}: {orphan_count}")


if __name__ == "__main__":
    conn = get_connection()
    try:
        accounts = seed_accounts(conn)
        seed_signup_changes(conn, accounts)
        seed_usage_events(conn, accounts)
        seed_invoices(conn, accounts)
        verify_referential_integrity(conn)
    finally:
        conn.close()

    print("Done. Database seeded.")