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
    """Background task: query latest readings from TimescaleDB and push to all WS clients every 500ms."""
    pool = await get_pool()
    while True:
        try:
            async with pool.acquire() as conn:
                # FIXED: Changed s.name AS sensor_code to s.sensor_code directly
                rows = await conn.fetch("""
                    SELECT DISTINCT ON (sensor_id) 
                        s.id, s.sensor_code, s.type, s.warn_threshold, s.crit_threshold,
                        r.value, r.time 
                    FROM readings r 
                    JOIN sensors s ON s.id = r.sensor_id 
                    ORDER BY sensor_id, r.time DESC
                """)
                
                payload = {
                    "type": "readings",
                    "data": [
                        {
                            "sensor_id": r["id"],
                            "sensor_code": r["sensor_code"],
                            "type": r["type"],
                            "value": r["value"],
                            "warn_threshold": r["warn_threshold"],
                            "crit_threshold": r["crit_threshold"],
                            "status": (
                                "critical" if r["value"] >= r["crit_threshold"] 
                                else "warning" if r["value"] >= r["warn_threshold"] 
                                else "normal"
                            ),
                            "time": r["time"].isoformat(),
                        } for r in rows
                    ]
                }
                await manager.broadcast(json.dumps(payload))
        except Exception as e:
            logger.error(f"Telemetry Broadcast loop error: {e}")
            
        await asyncio.sleep(0.5)

async def listen_for_alerts():
    """Background task: subscribe to Redis alerts channel, push to WS clients instantly on breach."""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("alerts")
    logger.info("🔊 Subscribed to Redis alerts channel successfully.")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                alert_data = json.loads(message["data"])
                payload = json.dumps({
                    "type": "alert",
                    "data": alert_data
                })
                await manager.broadcast(payload)
                logger.warning(f"🚨 Instant Alert pushed to {len(manager.active)} websocket clients")
    except asyncio.CancelledError:
        logger.info("Alert listener loop task shutting down.")
    finally:
        await pubsub.unsubscribe("alerts")

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Exposes the live bi-directional pipe node for client attachments."""
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive — client can send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)