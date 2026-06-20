import asyncio
import random
import logging
from datetime import datetime, timezone
from app.db.database import get_pool
from app.alerts.alert_engine import check_and_alert
from app.simulator import mitigation
from app.simulator import incident_tracker

logger = logging.getLogger(__name__)

SENSOR_CONFIG = {
    "methane":   {"base": 0.8,  "drift": 0.02, "min": 0.0,  "max": 4.0,   "spike_mag": 0.3, "spike_chance": 0.02},
    "temp":      {"base": 26.0, "drift": 0.08, "min": 20.0, "max": 45.0,  "spike_mag": 1.0, "spike_chance": 0.02},
    "vibration": {"base": 1.5,  "drift": 0.04, "min": 0.0,  "max": 15.0,  "spike_mag": 1.5, "spike_chance": 0.02},
    "co":        {"base": 20.0, "drift": 0.4,  "min": 0.0,  "max": 200.0, "spike_mag": 10.0, "spike_chance": 0.02},
}

_current_values = {}

def set_value(sensor_id: int, value: float):
    """Used by manual injection endpoint to override the simulator's internal state."""
    _current_values[sensor_id] = value

def next_value(sensor_id, sensor_type, warn_threshold=None):
    cfg = SENSOR_CONFIG[sensor_type]
    if sensor_id not in _current_values:
        _current_values[sensor_id] = cfg["base"]

    current = _current_values[sensor_id]

    if mitigation.is_active(sensor_id):
        # operator activated ventilation — pull strongly toward baseline
        strength = mitigation.MITIGATION_STRENGTH
        delta = (cfg["base"] - current) * strength
        new_val = current + delta
    elif warn_threshold is not None and current >= warn_threshold:
        # sensor is above warning threshold and NOT being ventilated —
        # hold near current elevated level with only tiny jitter, don't
        # let it silently drift back down on its own
        mitigation.mark_unresolved_spike(sensor_id)
        delta = random.uniform(-cfg["drift"] * 0.3, cfg["drift"] * 0.3)
        new_val = current + delta
    elif random.random() < cfg["spike_chance"]:
        delta = random.uniform(0, cfg["spike_mag"])
        new_val = current + delta
    else:
        delta = random.uniform(-cfg["drift"], cfg["drift"])
        new_val = current + delta

    new_val = max(cfg["min"], min(cfg["max"], new_val))
    _current_values[sensor_id] = new_val
    return round(new_val, 2)

async def run_simulator():
    pool = await get_pool()
    async with pool.acquire() as conn:
        sensors = await conn.fetch(
            "SELECT sensor_id, type, warn_threshold, crit_threshold FROM sensors"
        )
    logger.info(f"Simulator started — tracking {len(sensors)} sensors")

    while True:
        now = datetime.now(timezone.utc)
        rows = []
        for sensor in sensors:
            value = next_value(sensor["sensor_id"], sensor["type"], sensor["warn_threshold"])
            rows.append((now, sensor["sensor_id"], value))

            sid = sensor["sensor_id"]
            warn = sensor["warn_threshold"]
            crit = sensor["crit_threshold"]

            if value >= warn:
                await incident_tracker.record_breach(sid, value)
            elif incident_tracker.has_open_incident(sid):
                # value dropped back below warn threshold — resolved
                await incident_tracker.record_resolved(sid)

            await check_and_alert(
                sensor_id=sid,
                sensor_type=sensor["type"],
                value=value,
                warn_threshold=warn,
                crit_threshold=crit,
            )
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO readings (time, sensor_id, value) VALUES ($1, $2, $3)",
                rows
            )
        await asyncio.sleep(0.5)
