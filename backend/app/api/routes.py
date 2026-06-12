from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from app.db.database import get_pool

router = APIRouter()

# ── GET /sensors ───────────────────────────────────────────
@router.get("/sensors")
async def list_sensors():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, sensor_code, type, warn_threshold, crit_threshold
            FROM sensors 
            ORDER BY id
        """)
        return [
            {
                "id": r["id"],
                "sensor_code": r["sensor_code"],
                "type": r["type"],
                "warn_threshold": r["warn_threshold"],
                "crit_threshold": r["crit_threshold"]
            } for r in rows
        ]

# ── GET /sensors/{sensor_id}/readings ────────────────────────────
@router.get("/sensors/{sensor_id}/readings")
async def get_readings(
    sensor_id: int,
    from_time: datetime = Query(default=None, alias="from"),
    to_time: datetime = Query(default=None, alias="to"),
    limit: int = Query(default=200, le=1000),
):
    now = datetime.now(timezone.utc)
    from_time = from_time or now - timedelta(hours=1)
    to_time = to_time or now
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT id FROM sensors WHERE id = $1", sensor_id)
        if not exists:
            raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")
            
        rows = await conn.fetch("""
            SELECT time, value 
            FROM readings 
            WHERE sensor_id = $1 AND time BETWEEN $2 AND $3 
            ORDER BY time DESC 
            LIMIT $4
        """, sensor_id, from_time, to_time, limit)
        
        return {
            "sensor_id": sensor_id,
            "from": from_time.isoformat(),
            "to": to_time.isoformat(),
            "count": len(rows),
            "readings": [{"time": r["time"].isoformat(), "value": r["value"]} for r in rows]
        }

# ── GET /sensors/{sensor_id}/readings/aggregate ──────────────────
@router.get("/sensors/{sensor_id}/readings/aggregate")
async def get_aggregates(
    sensor_id: int,
    bucket: str = Query(default="5 minutes"),
    hours: int = Query(default=24, le=168),
):
    # This strict validation acts as our absolute firewall against SQL Injection
    if bucket not in ("5 minutes", "1 hour"):
        raise HTTPException(status_code=422, detail="Bucket must be '5 minutes' or '1 hour'")
        
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            # We hardcode the verified bucket string into the SQL text, bypassing the driver parameter parser completely
            query = f"""
                SELECT time_bucket(INTERVAL '{bucket}', time) AS bucket, 
                   AVG(value) AS avg_val, 
                   MAX(value) AS max_val, 
                   MIN(value) AS min_val 
                FROM readings 
                WHERE sensor_id = $1 AND time > NOW() - CAST($2 || ' hours' AS interval) 
                GROUP BY bucket 
                ORDER BY bucket DESC
            """
            rows = await conn.fetch(query, sensor_id, str(hours))
            
            return {
                "sensor_id": sensor_id,
                "bucket": bucket,
                "hours": hours,
                "data": [
                    {
                        "bucket": r["bucket"].isoformat() if r["bucket"] else None,
                        "avg": round(r["avg_val"], 2) if r["avg_val"] is not None else 0.0,
                        "max": round(r["max_val"], 2) if r["max_val"] is not None else 0.0,
                        "min": round(r["min_val"], 2) if r["min_val"] is not None else 0.0,
                    } for r in rows if r["bucket"] is not None
                ]
            }
        except Exception as db_err:
            print(f"❌ AGGREGATE CORE FAILURE: {db_err}")
            raise HTTPException(status_code=500, detail=f"Database Query Rejected: {str(db_err)}")
# ── GET /alerts ────────────────────────────────────────────
@router.get("/alerts")
async def list_alerts(
    severity: str = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if severity:
            rows = await conn.fetch("""
                SELECT a.id, a.severity, a.value, a.message, a.created_at, 
                       s.sensor_code, s.type
                FROM alerts a 
                JOIN sensors s ON s.id = a.sensor_id 
                WHERE a.severity = $1 
                ORDER BY a.created_at DESC 
                LIMIT $2
            """, severity, limit)
        else:
            rows = await conn.fetch("""
                SELECT a.id, a.severity, a.value, a.message, a.created_at, 
                       s.sensor_code, s.type
                FROM alerts a 
                JOIN sensors s ON s.id = a.sensor_id 
                ORDER BY a.created_at DESC 
                LIMIT $1
            """, limit)
        return [dict(r) for r in rows]

# ── POST /sensors/{id}/threshold ───────────────────────
class ThresholdUpdate(BaseModel):
    warn_threshold: float
    crit_threshold: float

@router.post("/sensors/{sensor_id}/threshold")
async def update_threshold(sensor_id: int, body: ThresholdUpdate):
    if body.warn_threshold >= body.crit_threshold:
        raise HTTPException(status_code=422, detail="warn_threshold must be less than crit_threshold")
        
    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchval("""
            UPDATE sensors 
            SET warn_threshold = $1, crit_threshold = $2 
            WHERE id = $3 
            RETURNING id
        """, body.warn_threshold, body.crit_threshold, sensor_id)
        
        if not updated:
            raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")
            
        return {"updated": True, "sensor_id": sensor_id}