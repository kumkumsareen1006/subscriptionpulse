```sql
-- ============================================================
-- SubscriptionPulse - Snowflake Setup
-- Configures warehouse, raw schema, S3 integration, staging,
-- source tables, and initial Parquet ingestion.
-- ============================================================


-- Warehouse and database setup

CREATE WAREHOUSE IF NOT EXISTS subscriptionpulse_wh
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

CREATE DATABASE IF NOT EXISTS subscriptionpulse;
CREATE SCHEMA IF NOT EXISTS subscriptionpulse.raw;

USE WAREHOUSE subscriptionpulse_wh;
USE DATABASE subscriptionpulse;
USE SCHEMA raw;


-- S3 storage integration
-- Replace the placeholder with the IAM role configured for Snowflake access.

CREATE STORAGE INTEGRATION IF NOT EXISTS subscriptionpulse_s3_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/snowflake-subscriptionpulse-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://subscriptionpulse-raw-kumkum/raw/');

-- Retrieve Snowflake integration details required by the AWS trust policy.
DESC STORAGE INTEGRATION subscriptionpulse_s3_int;

SELECT "property_value", LENGTH("property_value") AS arn_length
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "property" = 'STORAGE_AWS_IAM_USER_ARN';


-- External stage for Parquet files in S3

CREATE STAGE IF NOT EXISTS raw_stage
  URL = 's3://subscriptionpulse-raw-kumkum/raw/'
  STORAGE_INTEGRATION = subscriptionpulse_s3_int
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE);

-- Verify files available through the external stage.
LIST @raw_stage;


-- Raw source tables
-- _loaded_at records ingestion time separately from source updated_at.

CREATE TABLE IF NOT EXISTS accounts (
    account_id     INT,
    workspace_name STRING,
    contact_email  STRING,
    signup_date    DATE,
    plan_tier      STRING,
    status         STRING,
    updated_at     TIMESTAMP_NTZ,
    _loaded_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS usage_events (
    event_id   INT,
    account_id INT,
    event_type STRING,
    event_time TIMESTAMP_NTZ,
    updated_at TIMESTAMP_NTZ,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id     INT,
    account_id     INT,
    amount         NUMBER(8,2),
    invoice_date   DATE,
    payment_method STRING,
    status         STRING,
    updated_at     TIMESTAMP_NTZ,
    _loaded_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS subscription_changes (
    change_id   INT,
    account_id  INT,
    old_plan    STRING,
    new_plan    STRING,
    change_date DATE,
    updated_at  TIMESTAMP_NTZ,
    _loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- Load Parquet data into raw tables.
-- Column matching avoids dependency on physical column order.

COPY INTO accounts
  FROM @raw_stage/accounts/
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

COPY INTO usage_events
  FROM @raw_stage/usage_events/
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

COPY INTO invoices
  FROM @raw_stage/invoices/
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

COPY INTO subscription_changes
  FROM @raw_stage/subscription_changes/
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;


-- Validate raw table row counts.

SELECT 'accounts' AS table_name, COUNT(*) FROM accounts
UNION ALL
SELECT 'usage_events', COUNT(*) FROM usage_events
UNION ALL
SELECT 'invoices', COUNT(*) FROM invoices
UNION ALL
SELECT 'subscription_changes', COUNT(*) FROM subscription_changes;
```