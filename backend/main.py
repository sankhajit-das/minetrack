from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.database import run_schema, close_pool
from app.alerts.alert_engine import get_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup connection pools and schema for the web server
    await run_schema()
    await get_redis()
    print("Web API Gateway ready.")
    
    yield
    
    await close_pool()
    await close_redis()

app = FastAPI(title="MineTrack API", lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "MineTrack is running"}

@app.get("/health")
async def health():
    from app.db.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        sensors = await conn.fetchval("SELECT COUNT(*) FROM sensors")
        readings = await conn.fetchval("SELECT COUNT(*) FROM readings")
        alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts")
        
    return {
        "status": "ok",
        "sensors_in_db": sensors,
        "readings_in_db": readings,
        "alerts_in_db": alerts
    }