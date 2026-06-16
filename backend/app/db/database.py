import asyncio
import logging
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/minetrack")
_pool = None
logger = logging.getLogger("uvicorn.error")

async def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    for attempt in range(1, 11):
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
            logger.info("Connected to TimescaleDB.")
            return _pool
        except Exception as e:
            logger.warning(f"DB connection attempt {attempt}/10 failed. Retrying in 2s...")
            await asyncio.sleep(2)
    raise RuntimeError("Could not connect to TimescaleDB.")

async def run_schema():
    pool = await get_pool()
    async with pool.acquire() as conn:
        logger.info("Running schema...")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                id         SERIAL PRIMARY KEY,
                name       TEXT NOT NULL,
                level      INT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id      SERIAL PRIMARY KEY,
                zone_id        INT REFERENCES zones(id),
                sensor_code    TEXT NOT NULL UNIQUE,
                type           TEXT NOT NULL,
                unit           TEXT NOT NULL,
                warn_threshold FLOAT NOT NULL DEFAULT 0.0,
                crit_threshold FLOAT NOT NULL DEFAULT 0.0,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                time      TIMESTAMPTZ NOT NULL,
                sensor_id INT NOT NULL REFERENCES sensors(sensor_id),
                value     FLOAT NOT NULL
            );
        """)

        try:
            await conn.execute("SELECT create_hypertable('readings', 'time', if_not_exists => TRUE);")
        except Exception as e:
            logger.info(f"Hypertable note: {e}")

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
                ON readings (sensor_id, time DESC);
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id         SERIAL PRIMARY KEY,
                sensor_id  INT NOT NULL REFERENCES sensors(sensor_id),
                severity   TEXT NOT NULL,
                value      FLOAT NOT NULL,
                message    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            INSERT INTO zones (name, level) VALUES
                ('Main Entry', 1),
                ('Shaft A',    2),
                ('Heading C',  3)
            ON CONFLICT DO NOTHING;
        """)

        await conn.execute("""
            INSERT INTO sensors (zone_id, sensor_code, type, unit, warn_threshold, crit_threshold) VALUES
                (3, 'GAS-01', 'methane',   '%',       1.5,  2.5),
                (2, 'TMP-01', 'temp',      'celsius', 30.0, 35.0),
                (3, 'VIB-01', 'vibration', 'mm/s',    5.0,  8.0),
                (2, 'CO-01',  'co',        'ppm',     50.0, 100.0)
            ON CONFLICT DO NOTHING;
        """)

        logger.info("Schema ready. Zones, sensors, readings, alerts all set.")

async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
