FROM apache/airflow:3.3.1

# The pipeline's own dependencies (including dbt) live in a completely
# separate virtualenv, never installed into Airflow's own Python
# environment. dbt-core and Airflow pin conflicting versions of shared
# libraries (Jinja2, pydantic, etc.) — installing both together risks
# silently breaking Airflow itself.
RUN python3 -m venv /home/airflow/pipeline_venv
COPY requirements-airflow.txt /requirements-airflow.txt
RUN /home/airflow/pipeline_venv/bin/pip install --no-cache-dir -r /requirements-airflow.txt