import json
import logging
import redis.asyncio as aioredis
import os
from app.db.database import get_pool

logger = logging.getLogger(__name__)

_redis = None

async def get_redis():
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379"),
            encoding="utf-8",
            decode_responses=True
        )
    return _redis

async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None

COOLDOWN_SECONDS = 30

async def check_and_alert(
    sensor_id: int,
    sensor_type: str,
    value: float,
    warn_threshold: float,
    crit_threshold: float,
):
    # Determine anomaly status
    if value >= crit_threshold:
        severity = "critical"
        msg = f"{sensor_type.upper()} CRITICAL: {value} (threshold: {crit_threshold})"
    elif value >= warn_threshold:
        severity = "warning"
        msg = f"{sensor_type.upper()} WARNING: {value} (threshold: {warn_threshold})"
    else:
        return  # Everything safe, exit immediately

    # Use Redis keys to check for a live cooldown lock across containers
    r = await get_redis()
    cooldown_key = f"cooldown:sensor:{sensor_id}"
    
    # Check if a lock key exists for this sensor
    has_cooldown = await r.get(cooldown_key)
    if has_cooldown:
        return  # Cooldown active, suppress alert spam

    # Set the cooldown key with an automatic expiration time window
    await r.setex(cooldown_key, COOLDOWN_SECONDS, "locked")

    # 1. Write alert log record to TimescaleDB
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO alerts (sensor_id, severity, value, message) 
               VALUES ($1, $2, $3, $4)""",
            sensor_id, severity, value, msg
        )
        
    # 2. Publish to Redis channel live notification bus
    payload = json.dumps({
        "sensor_id": sensor_id,
        "type": sensor_type,
        "severity": severity,
        "value": value,
        "message": msg,
    })
    await r.publish("alerts", payload)
    logger.warning(f"🚨 ALERT REGISTERED: {msg}")