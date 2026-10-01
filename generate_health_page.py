"""
Generates the SubscriptionPulse pipeline health page.

Uses Snowflake for raw-layer row counts and load timestamps, and dbt
run_results.json for the latest test results. Run after dbt test so the
artifact reflects the most recent data-quality checks.

Writes the generated page to docs/index.html for GitHub Pages.
"""
 
import json
import os
from datetime import datetime, timezone
 
import snowflake.connector
from dotenv import load_dotenv
 
load_dotenv()
 
TABLES = ["accounts", "usage_events", "invoices", "subscription_changes"]
RUN_RESULTS_PATH = "subscriptionpulse_dbt/target/run_results.json"
OUTPUT_PATH = "docs/index.html"
 
 
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
 
 
def get_table_stats(cursor):
    """Return row counts and latest load timestamps from Snowflake."""
    stats = []
    for table in TABLES:
        cursor.execute(f"SELECT COUNT(*), MAX(_loaded_at) FROM {table}")
        count, last_loaded = cursor.fetchone()
        stats.append({"table": table, "rows": count, "last_loaded": last_loaded})
    return stats
 
 
def get_test_results():
    """Return pass/fail counts from the latest dbt run results."""
    if not os.path.exists(RUN_RESULTS_PATH):
        return None
    with open(RUN_RESULTS_PATH) as f:
        data = json.load(f)
    results = data.get("results", [])
    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "pass")
    return {"passed": passed, "total": total}
 
 
def render_html(table_stats, test_results):
    total_rows = sum(s["rows"] for s in table_stats)
    last_loaded_overall = max(s["last_loaded"] for s in table_stats)
 
    rows_html = "\n".join(
        f"<tr><td>{s['table']}</td><td>{s['rows']:,}</td>"
        f"<td>{s['last_loaded']}</td></tr>"
        for s in table_stats
    )
 
    if test_results:
        pct = round(100 * test_results["passed"] / test_results["total"], 1)
        test_line = f"{test_results['passed']} / {test_results['total']} ({pct}%)"
    else:
        test_line = "Run `dbt test` first"
 
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
 
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SubscriptionPulse &mdash; Pipeline Health</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 720px;
         margin: 48px auto; padding: 0 20px; color: #1a1a1a; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  .sub {{ color: #666; margin-bottom: 32px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0 32px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
  th {{ color: #666; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
  .stats {{ display: flex; gap: 32px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat .value {{ font-size: 1.6rem; font-weight: 700; }}
  .stat .label {{ color: #666; font-size: 0.85rem; }}
  a.docs-link {{ display: inline-block; margin-top: 8px; padding: 10px 18px;
                background: #1a1a1a; color: white; text-decoration: none;
                border-radius: 6px; }}
  footer {{ margin-top: 40px; color: #999; font-size: 0.8rem; }}
</style>
</head>
<body>
  <h1>SubscriptionPulse &mdash; Pipeline Health</h1>
  <div class="sub">Real numbers, pulled live from Snowflake and dbt &mdash; not estimates.</div>
 
  <div class="stats">
    <div class="stat">
      <div class="value">{total_rows:,}</div>
      <div class="label">Total rows in raw layer</div>
    </div>
    <div class="stat">
      <div class="value">{last_loaded_overall}</div>
      <div class="label">Last data load (UTC)</div>
    </div>
    <div class="stat">
      <div class="value">{test_line}</div>
      <div class="label">dbt tests passing</div>
    </div>
  </div>
 
  <table>
    <tr><th>Table</th><th>Rows</th><th>Last loaded</th></tr>
    {rows_html}
  </table>
 
  <a class="docs-link" href="./dbt/">View full dbt docs &rarr;</a>
 
  <footer>Generated {generated_at} by generate_health_page.py</footer>
</body>
</html>"""
 
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUTPUT_PATH}")
 
 
def main():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        table_stats = get_table_stats(cursor)
    finally:
        conn.close()
 
    test_results = get_test_results()
    render_html(table_stats, test_results)
 
 
if __name__ == "__main__":
    main()