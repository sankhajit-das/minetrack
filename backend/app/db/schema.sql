CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS zones (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    level      INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id       SERIAL PRIMARY KEY,
    zone_id         INT REFERENCES zones(id),
    sensor_code     TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL,
    unit            TEXT NOT NULL,
    warn_threshold  FLOAT NOT NULL DEFAULT 0.0,
    crit_threshold  FLOAT NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS readings (
    time       TIMESTAMPTZ NOT NULL,
    sensor_id  INT NOT NULL REFERENCES sensors(sensor_id),
    value      FLOAT NOT NULL
);

SELECT create_hypertable('readings', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
    ON readings (sensor_id, time DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id         SERIAL PRIMARY KEY,
    sensor_id  INT NOT NULL REFERENCES sensors(sensor_id),
    severity   TEXT NOT NULL,
    value      FLOAT NOT NULL,
    message    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO zones (name, level) VALUES
    ('Main Entry', 1),
    ('Shaft A',    2),
    ('Heading C',  3)
ON CONFLICT DO NOTHING;

INSERT INTO sensors (zone_id, sensor_code, type, unit, warn_threshold, crit_threshold) VALUES
    (3, 'GAS-01', 'methane',   '%',      1.5,  2.5),
    (2, 'TMP-01', 'temp',      'celsius', 30.0, 35.0),
    (3, 'VIB-01', 'vibration', 'mm/s',    5.0,  8.0),
    (2, 'CO-01',  'co',        'ppm',    50.0, 100.0)
ON CONFLICT DO NOTHING;
