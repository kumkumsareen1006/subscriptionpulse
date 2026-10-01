"""
Loads extracted Parquet data from the S3 external stage into Snowflake.

Each source table is loaded independently using COPY INTO. Snowflake's
file-load metadata prevents previously processed files from being loaded
again, allowing the load step to be rerun safely.

Connection settings are read from environment variables.
"""

import os

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

TABLES = ["accounts", "usage_events", "invoices", "subscription_changes"]


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "subscriptionpulse_wh"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "subscriptionpulse"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "raw"),
    )


def load_table(cursor, table_name):
    # Preserve Parquet logical types so timestamp values are interpreted correctly.
    cursor.execute(
        f"""
        COPY INTO {table_name}
          FROM @raw_stage/{table_name}/
          FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE = TRUE)
          MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
        """
    )
    results = cursor.fetchall()

    # A single summary row indicates that no new files were available to load.
    if len(results) == 1 and len(results[0]) == 1:
        print(f"{table_name}: {results[0][0]}")
        return

    # Report newly loaded files separately from files already processed by Snowflake.
    loaded = sum(1 for row in results if row[1] == "LOADED")
    skipped = sum(1 for row in results if row[1] == "LOAD_SKIPPED")
    print(f"{table_name}: {loaded} file(s) loaded, {skipped} already-loaded file(s) skipped")


def run_load():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for table_name in TABLES:
            load_table(cursor, table_name)
    finally:
        conn.close()
    print("Load run complete.")


if __name__ == "__main__":
    run_load()