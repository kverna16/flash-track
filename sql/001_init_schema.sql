-- FlashTrack initial schema
-- Grain: one row per day per location for flash/actuals tables

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL
);

CREATE TABLE members (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    join_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

CREATE TABLE daily_flash (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    projected_revenue NUMERIC(10, 2) NOT NULL,
    projected_attendance INTEGER NOT NULL,
    UNIQUE (date, location_id)
);

CREATE TABLE daily_actuals (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    actual_revenue NUMERIC(10, 2) NOT NULL,
    actual_attendance INTEGER NOT NULL,
    UNIQUE (date, location_id)
);

CREATE INDEX idx_daily_flash_date ON daily_flash(date);
CREATE INDEX idx_daily_actuals_date ON daily_actuals(date);
