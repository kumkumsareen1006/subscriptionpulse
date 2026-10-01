-- SubscriptionPulse: PostgreSQL source schema
-- Initialized automatically by the Postgres container on first startup.
-- Timestamps use UTC. Source records are not hard-deleted to support incremental extraction.


-- 1. accounts
-- Customer workspace and current subscription state.

CREATE TABLE accounts (
    account_id     SERIAL PRIMARY KEY,
    workspace_name TEXT NOT NULL,
    contact_email  TEXT NOT NULL UNIQUE,
    signup_date    DATE NOT NULL,
    plan_tier      TEXT NOT NULL CHECK (plan_tier IN ('starter', 'pro', 'enterprise')),
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'churned')),
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);


-- 2. usage_events
-- Append-only product activity log.

CREATE TABLE usage_events (
    event_id   SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES accounts(account_id),
    event_type TEXT NOT NULL,
    event_time TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);


-- 3. invoices
-- Append-only billing records. Status validation is handled downstream
-- through dbt accepted_values tests.

CREATE TABLE invoices (
    invoice_id     SERIAL PRIMARY KEY,
    account_id     INT NOT NULL REFERENCES accounts(account_id),
    amount         NUMERIC(8,2) NOT NULL,
    invoice_date   DATE NOT NULL,
    payment_method TEXT,
    status         TEXT NOT NULL DEFAULT 'paid',
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);


-- 4. subscription_changes
-- Append-only plan history. Initial signup records have a NULL old_plan.
-- Upgrade/downgrade classification is derived downstream in dbt.

CREATE TABLE subscription_changes (
    change_id   SERIAL PRIMARY KEY,
    account_id  INT NOT NULL REFERENCES accounts(account_id),
    old_plan    TEXT CHECK (old_plan IN ('starter', 'pro', 'enterprise')),
    new_plan    TEXT NOT NULL CHECK (new_plan IN ('starter', 'pro', 'enterprise')),
    change_date DATE NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- 5. _extract_watermarks
-- Stores the latest successfully extracted timestamp for each source table.
CREATE TABLE _extract_watermarks (
    table_name        TEXT PRIMARY KEY,
    last_extracted_at TIMESTAMP NOT NULL
);

-- Initialize watermarks at epoch so the first extraction includes all source records.
INSERT INTO _extract_watermarks (table_name, last_extracted_at) VALUES
    ('accounts',             '1970-01-01'),
    ('usage_events',         '1970-01-01'),
    ('invoices',             '1970-01-01'),
    ('subscription_changes', '1970-01-01')
ON CONFLICT (table_name) DO NOTHING;

-- Index updated_at columns used by incremental extraction queries.
CREATE INDEX idx_accounts_updated_at             ON accounts (updated_at);
CREATE INDEX idx_usage_events_updated_at         ON usage_events (updated_at);
CREATE INDEX idx_invoices_updated_at             ON invoices (updated_at);
CREATE INDEX idx_subscription_changes_updated_at ON subscription_changes (updated_at);

-- Maintain updated_at when account records change.
-- The trigger preserves explicitly supplied timestamps.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
        NEW.updated_at := now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_accounts_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();