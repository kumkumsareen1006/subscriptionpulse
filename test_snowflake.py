import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

try:
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            CURRENT_VERSION(),
            CURRENT_USER(),
            CURRENT_WAREHOUSE()
    """)

    version, user, warehouse = cursor.fetchone()

    print("SUCCESS: Connected to Snowflake!")
    print(f"Snowflake version: {version}")
    print(f"User: {user}")
    print(f"Warehouse: {warehouse}")

    cursor.close()
    conn.close()

except Exception as e:
    print("FAILED: Could not connect to Snowflake.")
    print(e)