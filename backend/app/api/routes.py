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
            SELECT sensor_id, sensor_code, type, unit, warn_threshold, crit_threshold
            FROM sensors
            ORDER BY sensor_id
        """)
        return [dict(r) for r in rows]

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
        exists = await conn.fetchval("SELECT sensor_id FROM sensors WHERE sensor_id = $1", sensor_id)
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
    if bucket not in ("5 minutes", "1 hour"):
        raise HTTPException(status_code=422, detail="Bucket must be '5 minutes' or '1 hour'")

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
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
            print(f"AGGREGATE FAILURE: {db_err}")
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
                JOIN sensors s ON s.sensor_id = a.sensor_id
                WHERE a.severity = $1
                ORDER BY a.created_at DESC
                LIMIT $2
            """, severity, limit)
        else:
            rows = await conn.fetch("""
                SELECT a.id, a.severity, a.value, a.message, a.created_at,
                       s.sensor_code, s.type
                FROM alerts a
                JOIN sensors s ON s.sensor_id = a.sensor_id
                ORDER BY a.created_at DESC
                LIMIT $1
            """, limit)
        return [dict(r) for r in rows]

# ── GET /zones ────────────────────────────────────────────
@router.get("/zones")
async def list_zones():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT z.id, z.name, z.level,
                   COUNT(s.sensor_id) AS sensor_count
            FROM zones z
            LEFT JOIN sensors s ON s.zone_id = z.id
            GROUP BY z.id, z.name, z.level
            ORDER BY z.level
        """)
    return [dict(r) for r in rows]

# ── GET /zones/{zone_id}/sensors ──────────────────────────
@router.get("/zones/{zone_id}/sensors")
async def zone_sensors(zone_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        zone = await conn.fetchval(
            "SELECT id FROM zones WHERE id = $1", zone_id
        )
        if not zone:
            raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sensor_id, sensor_code, type, unit,
                   warn_threshold, crit_threshold
            FROM sensors
            WHERE zone_id = $1
            ORDER BY sensor_id
        """, zone_id)
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
            WHERE sensor_id = $3
            RETURNING sensor_id
        """, body.warn_threshold, body.crit_threshold, sensor_id)

        if not updated:
            raise HTTPException(status_code=404, detail=f"Sensor {sensor_id} not found")

        return {"updated": True, "sensor_id": sensor_id}

# ── POST /sensors/{id}/inject — scenario injector for demos ─
@router.post("/sensors/{sensor_id}/inject")
async def inject_scenario(sensor_id: int, value: float):
    from app.alerts.alert_engine import check_and_alert
    from app.simulator import simulator as sim_module
    from app.simulator import mitigation

    pool = await get_pool()
    async with pool.acquire() as conn:
        sensor = await conn.fetchrow(
            "SELECT sensor_id, type, warn_threshold, crit_threshold FROM sensors WHERE sensor_id = $1",
            sensor_id
        )
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor not found")

        await conn.execute(
            "INSERT INTO readings (time, sensor_id, value) VALUES ($1, $2, $3)",
            datetime.now(timezone.utc), sensor_id, value
        )

    # critical fix: update the simulator's internal memory too,
    # otherwise the next tick ignores this injected spike entirely
    sim_module.set_value(sensor_id, value)
    mitigation.mark_unresolved_spike(sensor_id)

    await check_and_alert(
        sensor_id=sensor["sensor_id"],
        sensor_type=sensor["type"],
        value=value,
        warn_threshold=sensor["warn_threshold"],
        crit_threshold=sensor["crit_threshold"],
    )
    return {"injected": True, "sensor_id": sensor_id, "value": value}

# ── POST /sensors/{id}/ventilate — activate mitigation ──────
@router.post("/sensors/{sensor_id}/ventilate")
async def ventilate_sensor(sensor_id: int):
    from app.simulator import mitigation, incident_tracker
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT sensor_id FROM sensors WHERE sensor_id = $1", sensor_id
        )
    if not exists:
        raise HTTPException(status_code=404, detail="Sensor not found")
    mitigation.activate(sensor_id)
    await incident_tracker.record_ventilation(sensor_id)
    return {
        "activated": True,
        "sensor_id": sensor_id,
        "duration_seconds": mitigation.MITIGATION_DURATION
    }

# ── GET /incidents — operator response log ───────────────────
@router.get("/incidents")
async def list_incidents(limit: int = Query(default=20, le=100)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT i.id, i.breach_value, i.peak_value,
                   i.breach_at, i.ventilation_at, i.resolved_at,
                   s.sensor_code, s.type, s.unit
            FROM incidents i
            JOIN sensors s ON s.sensor_id = i.sensor_id
            ORDER BY i.breach_at DESC
            LIMIT $1
        """, limit)
    result = []
    for r in rows:
        response_seconds = None
        recovery_seconds = None
        if r["ventilation_at"]:
            response_seconds = round((r["ventilation_at"] - r["breach_at"]).total_seconds(), 1)
        if r["resolved_at"] and r["ventilation_at"]:
            recovery_seconds = round((r["resolved_at"] - r["ventilation_at"]).total_seconds(), 1)
        elif r["resolved_at"]:
            recovery_seconds = round((r["resolved_at"] - r["breach_at"]).total_seconds(), 1)
        result.append({
            "id": r["id"],
            "sensor_code": r["sensor_code"],
            "type": r["type"],
            "unit": r["unit"],
            "breach_value": r["breach_value"],
            "peak_value": r["peak_value"],
            "breach_at": r["breach_at"].isoformat(),
            "ventilation_at": r["ventilation_at"].isoformat() if r["ventilation_at"] else None,
            "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            "response_seconds": response_seconds,
            "recovery_seconds": recovery_seconds,
            "status": "resolved" if r["resolved_at"] else ("ventilating" if r["ventilation_at"] else "open"),
        })
    return result
