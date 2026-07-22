"""
FlashTrack daily pipeline.

Simulates a new day of flash/actual data landing, validates it, then checks
for anomalies and logs anything that needs attention.

Runs against the flashtrack_db Postgres container (the app database), which
is a *separate* database from Airflow's own metadata store. From inside an
Airflow container, the app database is reached via host.docker.internal
since it's published on the host machine's port 5432.
"""

from datetime import datetime, timedelta

import numpy as np
from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import create_engine, text

DB_CONN_STRING = "postgresql+psycopg2://flashtrack:flashtrack_dev_pw@host.docker.internal:5432/flashtrack"
NOISE_STD_DEV = 0.08

default_args = {
    "owner": "flashtrack",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def ingest_daily_data(**context):
    """Generate one new day of flash + actual data for every existing location."""
    engine = create_engine(DB_CONN_STRING)
    run_date = context["ds"]  # Airflow's logical date, e.g. '2026-07-22'

    with engine.begin() as conn:
        locations = conn.execute(text("SELECT id FROM locations")).fetchall()

        if not locations:
            raise ValueError("No locations found — has generate_data.py been run yet?")

        for (location_id,) in locations:
            # Base off this location's most recent flash entry, so trend continues
            last_flash = conn.execute(
                text("""
                    SELECT projected_revenue, projected_attendance
                    FROM daily_flash
                    WHERE location_id = :loc_id
                    ORDER BY date DESC
                    LIMIT 1
                """),
                {"loc_id": location_id},
            ).fetchone()

            base_revenue = float(last_flash[0]) if last_flash else 2500.0
            base_attendance = int(last_flash[1]) if last_flash else 150

            projected_revenue = round(base_revenue * np.random.uniform(0.98, 1.03), 2)
            projected_attendance = int(base_attendance * np.random.uniform(0.98, 1.03))

            conn.execute(
                text("""
                    INSERT INTO daily_flash (date, location_id, projected_revenue, projected_attendance)
                    VALUES (:date, :loc_id, :rev, :att)
                    ON CONFLICT (date, location_id) DO NOTHING
                """),
                {"date": run_date, "loc_id": location_id, "rev": projected_revenue, "att": projected_attendance},
            )

            revenue_noise = np.random.normal(loc=0, scale=NOISE_STD_DEV)
            attendance_noise = np.random.normal(loc=0, scale=NOISE_STD_DEV)

            actual_revenue = round(projected_revenue * (1 + revenue_noise), 2)
            actual_attendance = max(0, int(projected_attendance * (1 + attendance_noise)))

            conn.execute(
                text("""
                    INSERT INTO daily_actuals (date, location_id, actual_revenue, actual_attendance)
                    VALUES (:date, :loc_id, :rev, :att)
                    ON CONFLICT (date, location_id) DO NOTHING
                """),
                {"date": run_date, "loc_id": location_id, "rev": actual_revenue, "att": actual_attendance},
            )

    print(f"Ingested data for {run_date} across {len(locations)} locations.")


def validate_data(**context):
    """Fail the pipeline loudly if today's data is missing or malformed."""
    engine = create_engine(DB_CONN_STRING)
    run_date = context["ds"]

    with engine.connect() as conn:
        flash_count = conn.execute(
            text("SELECT COUNT(*) FROM daily_flash WHERE date = :d"), {"d": run_date}
        ).scalar()
        actuals_count = conn.execute(
            text("SELECT COUNT(*) FROM daily_actuals WHERE date = :d"), {"d": run_date}
        ).scalar()
        location_count = conn.execute(text("SELECT COUNT(*) FROM locations")).scalar()

        null_check = conn.execute(
            text("""
                SELECT COUNT(*) FROM daily_actuals
                WHERE date = :d AND (actual_revenue IS NULL OR actual_revenue < 0)
            """),
            {"d": run_date},
        ).scalar()

    if flash_count != location_count or actuals_count != location_count:
        raise ValueError(
            f"Row count mismatch for {run_date}: expected {location_count} locations, "
            f"got {flash_count} flash rows and {actuals_count} actuals rows."
        )

    if null_check > 0:
        raise ValueError(f"Found {null_check} invalid (null/negative) actual_revenue rows for {run_date}.")

    print(f"Validation passed for {run_date}: {flash_count} flash rows, {actuals_count} actuals rows, all valid.")


def check_anomalies(**context):
    """Query the flagged_anomalies view for today and log anything found."""
    engine = create_engine(DB_CONN_STRING)
    run_date = context["ds"]

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT location_name, revenue_variance_pct, anomaly_type FROM flagged_anomalies WHERE date = :d"),
            {"d": run_date},
        ).fetchall()

    if not rows:
        print(f"No anomalies flagged for {run_date}.")
    else:
        print(f"{len(rows)} anomaly(ies) flagged for {run_date}:")
        for location_name, variance_pct, anomaly_type in rows:
            print(f"  - {location_name}: {variance_pct}% ({anomaly_type})")


with DAG(
    dag_id="flashtrack_daily_pipeline",
    default_args=default_args,
    description="Ingest daily flash/actual data, validate it, and flag anomalies",
    schedule_interval="@daily",
    start_date=datetime(2026, 7, 20),
    catchup=False,
    tags=["flashtrack"],
) as dag:

    ingest_task = PythonOperator(
        task_id="ingest_daily_data",
        python_callable=ingest_daily_data,
    )

    validate_task = PythonOperator(
        task_id="validate_data",
        python_callable=validate_data,
    )

    anomaly_check_task = PythonOperator(
        task_id="check_anomalies",
        python_callable=check_anomalies,
    )

    ingest_task >> validate_task >> anomaly_check_task
