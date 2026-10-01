"""
Incremental extraction pipeline for SubscriptionPulse.

Extracts new or updated rows from PostgreSQL using per-table watermarks,
writes the results to Parquet, and uploads them to date-partitioned S3
locations. Watermarks advance only after a successful upload.

AWS credentials are loaded from the environment.
"""

import os
from datetime import datetime

import boto3
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables used by AWS and database connections.
load_dotenv()


# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

# POSTGRES_HOST can be overridden when running from another container.
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_URL = f"postgresql+psycopg2://postgres:postgres@{DB_HOST}:5433/subscriptionpulse"
S3_BUCKET = "subscriptionpulse-raw-kumkum"

# Fixed table list prevents dynamic table names from accepting external input.
TABLES = ["accounts", "usage_events", "invoices", "subscription_changes"]

LOCAL_TMP_DIR = "tmp_extract"


def get_watermark(engine, table_name):
    """Return the last successfully extracted timestamp for a source table."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT last_extracted_at FROM _extract_watermarks WHERE table_name = :t"),
            {"t": table_name},
        )
        return result.fetchone()[0]


def extract_new_rows(engine, table_name, watermark):
    """Extract rows modified after the table's current watermark."""
    query = text(f"SELECT * FROM {table_name} WHERE updated_at > :wm ORDER BY updated_at")
    return pd.read_sql(query, engine, params={"wm": watermark})


def write_parquet(df, table_name):
    os.makedirs(LOCAL_TMP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{table_name}_{timestamp}.parquet"
    local_path = os.path.join(LOCAL_TMP_DIR, filename)
    df.to_parquet(local_path, engine="pyarrow", index=False)
    return local_path, filename


def upload_to_s3(local_path, table_name, extract_date, filename):
    """Upload a Parquet extract using table and extraction date partitions."""
    s3 = boto3.client("s3")
    key = f"raw/{table_name}/extract_date={extract_date}/{filename}"
    s3.upload_file(local_path, S3_BUCKET, key)
    return key


def update_watermark(engine, table_name, new_watermark):
    """Advance the watermark to the latest timestamp included in the extract."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE _extract_watermarks SET last_extracted_at = :wm WHERE table_name = :t"),
            {"wm": new_watermark, "t": table_name},
        )


def run_extract():
    if S3_BUCKET == "REPLACE_WITH_YOUR_BUCKET_NAME":
        raise SystemExit("Set S3_BUCKET in extract.py to your actual S3 bucket name before running.")

    engine = create_engine(DB_URL)
    extract_date = datetime.now().date()

    for table_name in TABLES:
        watermark = get_watermark(engine, table_name)
        df = extract_new_rows(engine, table_name, watermark)

        if df.empty:
            print(f"{table_name}: no new rows since {watermark} — watermark unchanged")
            continue

        local_path, filename = write_parquet(df, table_name)
        s3_key = upload_to_s3(local_path, table_name, extract_date, filename)
        os.remove(local_path)  # Remove local extract after successful S3 upload.

        new_watermark = df["updated_at"].max().to_pydatetime()
        update_watermark(engine, table_name, new_watermark)

        print(
            f"{table_name}: {len(df)} rows extracted "
            f"(watermark {watermark} -> {new_watermark}), "
            f"uploaded to s3://{S3_BUCKET}/{s3_key}"
        )

    print("Extract run complete.")


if __name__ == "__main__":
    run_extract()