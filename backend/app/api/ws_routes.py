import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.ws_manager import manager
from app.db.database import get_pool
from app.alerts.alert_engine import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()

async def broadcast_sensor_data():
    pool = await get_pool()
    while True:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT ON (r.sensor_id)
                        s.sensor_id, s.sensor_code, s.type, s.unit,
                        s.warn_threshold, s.crit_threshold,
                        z.name AS zone_name,
                        r.value, r.time
                    FROM readings r
                    JOIN sensors s ON s.sensor_id = r.sensor_id
                    JOIN zones z ON z.id = s.zone_id
                    ORDER BY r.sensor_id, r.time DESC
                """)
            if rows:
                payload = {
                    "type": "readings",
                    "data": [
                        {
                            "sensor_id":      r["sensor_id"],
                            "sensor_code":    r["sensor_code"],
                            "type":           r["type"],
                            "unit":           r["unit"],
                            "zone":           r["zone_name"],
                            "value":          r["value"],
                            "warn_threshold": r["warn_threshold"],
                            "crit_threshold": r["crit_threshold"],
                            "status": (
                                "critical" if r["value"] >= r["crit_threshold"]
                                else "warning" if r["value"] >= r["warn_threshold"]
                                else "normal"
                            ),
                            "time": r["time"].isoformat(),
                        }
                        for r in rows
                    ]
                }
                await manager.broadcast(json.dumps(payload))
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
        await asyncio.sleep(0.5)

async def listen_for_alerts():
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("alerts")
    logger.info("Subscribed to Redis alerts channel")
    async for message in pubsub.listen():
        if message["type"] == "message":
            alert_data = json.loads(message["data"])
            payload = json.dumps({"type": "alert", "data": alert_data})
            await manager.broadcast(payload)

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
