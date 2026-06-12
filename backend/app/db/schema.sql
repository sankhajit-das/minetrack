-- enable TimescaleDB extension 
CREATE EXTENSION IF NOT EXISTS timescaledb; 

-- zones: physical areas of the mine 
CREATE TABLE IF NOT EXISTS zones ( 
    id SERIAL PRIMARY KEY, 
    name TEXT NOT NULL, 
    level INT NOT NULL, 
    created_at TIMESTAMPTZ DEFAULT NOW() 
); 

-- sensors: one row per physical sensor device 
CREATE TABLE IF NOT EXISTS sensors ( 
    id SERIAL PRIMARY KEY, 
    zone_id INT REFERENCES zones(id), 
    sensor_code TEXT NOT NULL UNIQUE, 
    type TEXT NOT NULL, -- 'methane' | 'temp' | 'vibration' | 'co' 
    unit TEXT NOT NULL, -- '%' | 'celsius' | 'mm/s' | 'ppm' 
    warn_threshold FLOAT NOT NULL, 
    crit_threshold FLOAT NOT NULL, 
    created_at TIMESTAMPTZ DEFAULT NOW() 
); 

-- readings: every sensor reading — this becomes a hypertable 
CREATE TABLE IF NOT EXISTS readings ( 
    time TIMESTAMPTZ NOT NULL, 
    sensor_id INT NOT NULL REFERENCES sensors(id), 
    value FLOAT NOT NULL 
); 

-- convert readings to a TimescaleDB hypertable (partitioned by time) 
SELECT create_hypertable('readings', 'time', if_not_exists => TRUE); 

-- index for fast per-sensor queries 
CREATE INDEX IF NOT EXISTS idx_readings_sensor_time ON readings (sensor_id, time DESC); 

-- alerts: logged every time a threshold is breached 
CREATE TABLE IF NOT EXISTS alerts ( 
    id SERIAL PRIMARY KEY, 
    sensor_id INT NOT NULL REFERENCES sensors(id), 
    severity TEXT NOT NULL, -- 'warning' | 'critical' 
    value FLOAT NOT NULL, 
    message TEXT NOT NULL, 
    created_at TIMESTAMPTZ DEFAULT NOW() 
); 

-- seed: 3 zones 
INSERT INTO zones (name, level) 
VALUES 
    ('Main Entry', 1), 
    ('Shaft A', 2), 
    ('Heading C', 3) 
ON CONFLICT DO NOTHING; 

-- seed: 4 sensors (one per type) 
INSERT INTO sensors (zone_id, sensor_code, type, unit, warn_threshold, crit_threshold) 
VALUES 
    (3, 'GAS-01', 'methane', '%', 0.1, 2.5), 
    (2, 'TMP-01', 'temp', 'celsius', 30.0, 35.0), 
    (3, 'VIB-01', 'vibration', 'mm/s', 5.0, 8.0), 
    (2, 'CO-01', 'co', 'ppm', 50.0, 100.0) 
ON CONFLICT DO NOTHING;