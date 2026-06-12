import asyncio
import random
import logging
from datetime import datetime, timezone
from app.db.database import get_pool
from app.alerts.alert_engine import check_and_alert

logger = logging.getLogger(__name__)

# realistic base values and drift limits per sensor type
SENSOR_CONFIG = {
    "methane": {"base": 0.8, "drift": 0.05, "min": 0.0, "max": 4.0, "spike_mag": 0.8},
    "temp": {"base": 26.0, "drift": 0.2, "min": 20.0, "max": 45.0, "spike_mag": 3.0},
    "vibration": {"base": 1.5, "drift": 0.1, "min": 0.0, "max": 15.0, "spike_mag": 4.0},
    "co": {"base": 20.0, "drift": 1.0, "min": 0.0, "max": 200.0, "spike_mag": 30.0},
}

# track current value per sensor so readings drift smoothly
_current_values: dict[int, float] = {}

def next_value(sensor_id: int, sensor_type: str) -> float:
    """Generate next reading using random walk with occasional spikes."""
    cfg = SENSOR_CONFIG[sensor_type]
    
    # initialise on first call
    if sensor_id not in _current_values:
        _current_values[sensor_id] = cfg["base"]
    
    current = _current_values[sensor_id]
    
    # 5% chance of a spike — simulates real mine events
    if random.random() < 0.05:
        delta = random.uniform(0, cfg["spike_mag"])
    else:
        # normal drift: small random walk
        delta = random.uniform(-cfg["drift"], cfg["drift"])
    
    new_val = current + delta
    # clamp to realistic sensor range
    new_val = max(cfg["min"], min(cfg["max"], new_val))
    _current_values[sensor_id] = new_val
    return round(new_val, 2)

async def run_simulator():
    """Continuously generates sensor readings every 500ms."""
    pool = await get_pool()
    
    # load all sensors once at startup
    async with pool.acquire() as conn:
        sensors = await conn.fetch(
            "SELECT id, type, warn_threshold, crit_threshold FROM sensors"
        )
    logger.info(f"Simulator started — tracking {len(sensors)} sensors")
    
    while True:
        now = datetime.now(timezone.utc)
        rows = []
        for sensor in sensors:
            value = next_value(sensor["id"], sensor["type"])
            rows.append((now, sensor["id"], value))
            
            # check thresholds and fire alert if breached
            await check_and_alert(
                sensor_id=sensor["id"],
                sensor_type=sensor["type"],
                value=value,
                warn_threshold=sensor["warn_threshold"],
                crit_threshold=sensor["crit_threshold"],
            )
            
        # batch insert all readings in one query
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO readings (time, sensor_id, value) VALUES ($1, $2, $3)", 
                rows
            )
        await asyncio.sleep(0.5) # 500ms interval