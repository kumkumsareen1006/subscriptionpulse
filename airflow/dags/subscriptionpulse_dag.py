"""
Orchestrates the daily SubscriptionPulse pipeline:
extract -> load -> dbt snapshot -> dbt run -> dbt test.

Pipeline commands run in an isolated virtual environment to avoid
dependency conflicts with Airflow.
"""

import os
from datetime import datetime, timedelta

import requests
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PROJECT_DIR = "/opt/airflow/subscriptionpulse"
DBT_DIR = f"{PROJECT_DIR}/subscriptionpulse_dbt"
VENV_PYTHON = "/home/airflow/pipeline_venv/bin/python"
VENV_DBT = "/home/airflow/pipeline_venv/bin/dbt"


def alert_slack_on_failure(context):
    """Send a Slack failure alert when SLACK_WEBHOOK_URL is configured."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not set — skipping Slack alert.")
        return

    task_id = context["task_instance"].task_id
    dag_id = context["dag"].dag_id
    run_id = context["run_id"]
    message = f":x: *{dag_id}* failed on task `{task_id}` (run: {run_id})"

    try:
        requests.post(webhook_url, json={"text": message}, timeout=10)
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")


default_args = {
    "owner": "kumkum",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": alert_slack_on_failure,
}

with DAG(
    dag_id="subscriptionpulse_pipeline",
    default_args=default_args,
    description="extract -> load raw -> dbt run (staging)",
    schedule="@daily",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    tags=["subscriptionpulse"],
) as dag:

    extract = BashOperator(
        task_id="extract",
        bash_command=f"cd {PROJECT_DIR} && {VENV_PYTHON} extract.py",
    )

    load_to_snowflake = BashOperator(
        task_id="load_to_snowflake",
        bash_command=f"cd {PROJECT_DIR} && {VENV_PYTHON} load_to_snowflake.py",
    )

    # Run snapshots separately to maintain account history before model builds.
    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f"cd {DBT_DIR} && {VENV_DBT} snapshot --profiles-dir .",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {VENV_DBT} run --profiles-dir .",
    )

    # Data-quality failures are deterministic, so tests do not retry.
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {VENV_DBT} test --profiles-dir .",
        retries=0,
    )

    extract >> load_to_snowflake >> dbt_snapshot >> dbt_run >> dbt_test
