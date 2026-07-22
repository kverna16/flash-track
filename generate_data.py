"""
FlashTrack synthetic data generator.

Generates realistic membership/location data plus daily flash (projected)
and actuals (real) revenue/attendance figures, then loads everything into
the Postgres database started via docker-compose.

Noise model (documented so you can explain it in an interview):
- Each location has a baseline daily revenue/attendance figure.
- "Flash" projections are the baseline with small day-to-day trend drift.
- "Actuals" are the flash number multiplied by a random noise factor drawn
  from a normal distribution (mean 0, ~8% std dev), simulating the natural
  variance between what was projected and what actually happened.
"""

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NUM_LOCATIONS = 4
DAYS_OF_HISTORY = 90  # 3 months
MEMBERS_PER_LOCATION = (150, 400)  # random range per location
NOISE_STD_DEV = 0.08  # 8% typical variance between flash and actual

DB_CONN_STRING = "postgresql+psycopg2://flashtrack:flashtrack_dev_pw@localhost:5432/flashtrack"

fake = Faker()
random.seed(42)
np.random.seed(42)

CITIES = ["New York, NY", "Brooklyn, NY", "Jersey City, NJ", "Hoboken, NJ", "Queens, NY"]


def generate_locations(n):
    rows = []
    for i in range(n):
        rows.append({
            "name": f"{fake.city_prefix()} {fake.street_suffix()} Club",
            "city": CITIES[i % len(CITIES)],
        })
    return pd.DataFrame(rows)


def generate_members(location_ids):
    rows = []
    for loc_id in location_ids:
        n_members = random.randint(*MEMBERS_PER_LOCATION)
        for _ in range(n_members):
            join_date = fake.date_between(start_date="-2y", end_date="today")
            status = np.random.choice(
                ["active", "cancelled", "frozen"], p=[0.78, 0.17, 0.05]
            )
            rows.append({
                "location_id": loc_id,
                "join_date": join_date,
                "status": status,
            })
    return pd.DataFrame(rows)


def generate_daily_flash_and_actuals(location_ids):
    flash_rows = []
    actual_rows = []

    start_date = date.today() - timedelta(days=DAYS_OF_HISTORY)

    for loc_id in location_ids:
        # Each location gets its own baseline so locations aren't identical
        base_revenue = random.uniform(1800, 4500)
        base_attendance = random.uniform(80, 220)

        for day_offset in range(DAYS_OF_HISTORY):
            current_date = start_date + timedelta(days=day_offset)

            # Slight upward/downward trend drift over the period
            trend_factor = 1 + (day_offset / DAYS_OF_HISTORY) * random.uniform(-0.05, 0.15)

            # Weekday dip is NOT modeled here since we chose simple noise —
            # every day uses the same baseline plus random noise only.
            projected_revenue = round(base_revenue * trend_factor, 2)
            projected_attendance = int(base_attendance * trend_factor)

            flash_rows.append({
                "date": current_date,
                "location_id": loc_id,
                "projected_revenue": projected_revenue,
                "projected_attendance": projected_attendance,
            })

            # Actuals = flash + random noise
            revenue_noise = np.random.normal(loc=0, scale=NOISE_STD_DEV)
            attendance_noise = np.random.normal(loc=0, scale=NOISE_STD_DEV)

            actual_revenue = round(projected_revenue * (1 + revenue_noise), 2)
            actual_attendance = max(0, int(projected_attendance * (1 + attendance_noise)))

            actual_rows.append({
                "date": current_date,
                "location_id": loc_id,
                "actual_revenue": actual_revenue,
                "actual_attendance": actual_attendance,
            })

    return pd.DataFrame(flash_rows), pd.DataFrame(actual_rows)


def main():
    engine = create_engine(DB_CONN_STRING)

    print("Generating locations...")
    locations_df = generate_locations(NUM_LOCATIONS)
    locations_df.to_sql("locations", engine, if_exists="append", index=False)

    # Pull back the auto-generated IDs so members/flash/actuals can reference them
    location_ids = pd.read_sql("SELECT id FROM locations", engine)["id"].tolist()

    print("Generating members...")
    members_df = generate_members(location_ids)
    members_df.to_sql("members", engine, if_exists="append", index=False)

    print("Generating daily flash and actuals...")
    flash_df, actuals_df = generate_daily_flash_and_actuals(location_ids)
    flash_df.to_sql("daily_flash", engine, if_exists="append", index=False)
    actuals_df.to_sql("daily_actuals", engine, if_exists="append", index=False)

    print(f"Done. Loaded {len(locations_df)} locations, {len(members_df)} members, "
          f"{len(flash_df)} flash rows, {len(actuals_df)} actual rows.")


if __name__ == "__main__":
    main()
