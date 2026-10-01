"""
Generates ongoing activity for the SubscriptionPulse source database.

Simulates daily account signups, product usage, invoicing, plan changes,
and account status changes. These changes provide source data for testing
incremental extraction based on updated_at.

Usage:
    python simulate.py
    python simulate.py 14
    python simulate.py 60 7
"""

import random
import sys
from datetime import datetime, timedelta

import psycopg2
from faker import Faker


fake = Faker()


DB_CONFIG = {
    "host": "localhost",
    "port": 5433,  # Docker maps host port 5433 to PostgreSQL port 5432
    "dbname": "subscriptionpulse",
    "user": "postgres",
    "password": "postgres",
}


DEFAULT_DAYS = 7


EVENT_TYPES = [
    "login",
    "task_created",
    "task_completed",
    "comment_added",
    "teammate_invited",
    "board_created",
]

PLAN_TIERS = ["starter", "pro", "enterprise"]
MONTHLY_PRICE_BY_TIER = {"starter": 9.00, "pro": 29.00, "enterprise": 99.00}


# Daily probabilities used to generate incremental account activity.
NEW_ACCOUNTS_PER_DAY = (0, 3)
ODDS_PLAN_CHANGE = 0.02          # active account changes plan
ODDS_PAUSE = 0.01                # active -> paused
ODDS_CHURN_FROM_ACTIVE = 0.005   # active -> churned
ODDS_REACTIVATE = 0.20           # paused -> active
ODDS_CHURN_FROM_PAUSED = 0.05    # paused -> churned
ODDS_INVOICE = 1 / 30            # approximate monthly billing frequency


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_accounts_by_status(conn, statuses):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT account_id, plan_tier, status FROM accounts WHERE status = ANY(%s)",
            (list(statuses),),
        )
        return cur.fetchall()


def simulate_new_signups(conn, sim_date):
    """Create new accounts and record their initial subscription state."""
    n = random.randint(*NEW_ACCOUNTS_PER_DAY)
    for _ in range(n):
        workspace_name = fake.company()
        contact_email = fake.unique.company_email()
        plan_tier = random.choices(PLAN_TIERS, weights=[0.50, 0.35, 0.15])[0]
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO accounts (workspace_name, contact_email, signup_date, plan_tier, status)
                VALUES (%s, %s, %s, %s, 'active')
                RETURNING account_id
                """,
                (workspace_name, contact_email, sim_date, plan_tier),
            )
            account_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO subscription_changes (account_id, old_plan, new_plan, change_date)
                VALUES (%s, NULL, %s, %s)
                """,
                (account_id, plan_tier, sim_date),
            )
    conn.commit()
    return n


def simulate_usage_events(conn, sim_datetime):
    """Generate product usage events for active accounts."""
    accounts = get_accounts_by_status(conn, ["active"])
    rows = []
    for account_id, _plan_tier, _status in accounts:
        for _ in range(random.randint(0, 5)):
            event_time = sim_datetime + timedelta(
                hours=random.randint(0, 23), minutes=random.randint(0, 59)
            )
            rows.append((account_id, random.choice(EVENT_TYPES), event_time))
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO usage_events (account_id, event_type, event_time) VALUES (%s, %s, %s)",
                rows,
            )
        conn.commit()
    return len(rows)


def simulate_invoices(conn, sim_date):
    """Generate invoices for active and paused subscriptions."""
    accounts = get_accounts_by_status(conn, ["active", "paused"])
    rows = []
    for account_id, plan_tier, _status in accounts:
        if random.random() < ODDS_INVOICE:
            amount = round(MONTHLY_PRICE_BY_TIER[plan_tier] * random.uniform(0.95, 1.05), 2)
            status = random.choices(["paid", "failed", "refunded"], weights=[0.90, 0.07, 0.03])[0]
            payment_method = random.choice(["credit_card", "paypal", "bank_transfer"])
            rows.append((account_id, amount, sim_date, payment_method, status))
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO invoices (account_id, amount, invoice_date, payment_method, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()
    return len(rows)


def simulate_plan_changes(conn, sim_date):
    """Apply plan changes and record subscription history."""
    accounts = get_accounts_by_status(conn, ["active"])
    count = 0
    for account_id, plan_tier, _status in accounts:
        if random.random() < ODDS_PLAN_CHANGE:
            new_plan = random.choice([t for t in PLAN_TIERS if t != plan_tier])
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subscription_changes (account_id, old_plan, new_plan, change_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (account_id, plan_tier, new_plan, sim_date),
                )
                cur.execute(
                    "UPDATE accounts SET plan_tier = %s WHERE account_id = %s",
                    (new_plan, account_id),
                )
            count += 1
    conn.commit()
    return count


def simulate_status_changes(conn, sim_date):
    """Simulate account transitions between active, paused, and churned states."""
    changes = 0

    for account_id, _plan_tier, _status in get_accounts_by_status(conn, ["active"]):
        roll = random.random()
        new_status = None
        if roll < ODDS_CHURN_FROM_ACTIVE:
            new_status = "churned"
        elif roll < ODDS_CHURN_FROM_ACTIVE + ODDS_PAUSE:
            new_status = "paused"
        if new_status:
            with conn.cursor() as cur:
                cur.execute("UPDATE accounts SET status = %s WHERE account_id = %s", (new_status, account_id))
            changes += 1

    for account_id, _plan_tier, _status in get_accounts_by_status(conn, ["paused"]):
        roll = random.random()
        new_status = None
        if roll < ODDS_CHURN_FROM_PAUSED:
            new_status = "churned"
        elif roll < ODDS_CHURN_FROM_PAUSED + ODDS_REACTIVATE:
            new_status = "active"
        if new_status:
            with conn.cursor() as cur:
                cur.execute("UPDATE accounts SET status = %s WHERE account_id = %s", (new_status, account_id))
            changes += 1

    conn.commit()
    return changes


if __name__ == "__main__":
    num_days = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DAYS
    start_offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    conn = get_connection()
    try:
        for day in range(start_offset, start_offset + num_days):
            sim_datetime = datetime.now() + timedelta(days=day)
            sim_date = sim_datetime.date()

            new_accounts = simulate_new_signups(conn, sim_date)
            new_events = simulate_usage_events(conn, sim_datetime)
            new_invoices = simulate_invoices(conn, sim_date)
            plan_changes = simulate_plan_changes(conn, sim_date)
            status_changes = simulate_status_changes(conn, sim_date)

            print(
                f"Day {day + 1} ({sim_date}): "
                f"{new_accounts} new accounts, {new_events} events, "
                f"{new_invoices} invoices, {plan_changes} plan changes, "
                f"{status_changes} status changes"
            )
    finally:
        conn.close()

    print("Done. Simulation complete.")