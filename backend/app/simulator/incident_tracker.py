import logging
from datetime import datetime, timezone
from app.db.database import get_pool

logger = logging.getLogger(__name__)

# sensor_id -> open incident id (None if no active incident)
_open_incidents = {}

async def record_breach(sensor_id: int, value: float):
    """Called when a sensor first crosses warn/crit threshold."""
    if sensor_id in _open_incidents:
        # already tracking an open incident — update peak if higher
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE incidents SET peak_value = GREATEST(peak_value, $1) WHERE id = $2",
                value, _open_incidents[sensor_id]
            )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        incident_id = await conn.fetchval(
            """INSERT INTO incidents (sensor_id, breach_value, peak_value, breach_at)
               VALUES ($1, $2, $2, NOW()) RETURNING id""",
            sensor_id, value
        )
    _open_incidents[sensor_id] = incident_id
    logger.warning(f"Incident #{incident_id} opened for sensor {sensor_id}")

async def record_ventilation(sensor_id: int):
    """Called when operator activates ventilation for a sensor with an open incident."""
    if sensor_id not in _open_incidents:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE incidents SET ventilation_at = NOW() WHERE id = $1",
            _open_incidents[sensor_id]
        )

async def record_resolved(sensor_id: int):
    """Called when a sensor's value returns to normal range."""
    if sensor_id not in _open_incidents:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE incidents SET resolved_at = NOW() WHERE id = $1",
            _open_incidents[sensor_id]
        )
    logger.info(f"Incident #{_open_incidents[sensor_id]} resolved for sensor {sensor_id}")
    del _open_incidents[sensor_id]

def has_open_incident(sensor_id: int) -> bool:
    return sensor_id in _open_incidents
