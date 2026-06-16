import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.database import run_schema, close_pool
from app.simulator.simulator import run_simulator
from app.api.ws_routes import router as ws_router, broadcast_sensor_data, listen_for_alerts
from app.api.routes import router as api_router

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_schema()
    print("DB schema ready")
    tasks = [
        asyncio.create_task(run_simulator()),
        asyncio.create_task(broadcast_sensor_data()),
        asyncio.create_task(listen_for_alerts()),
    ]
    print("Simulator + WebSocket broadcaster + alert listener running")
    yield
    for t in tasks:
        t.cancel()
    await close_pool()

app = FastAPI(title="MineTrack API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(api_router)

@app.get("/")
async def root():
    return {"status": "MineTrack is running"}

@app.get("/health")
async def health():
    from app.db.database import get_pool
    from app.api.ws_manager import manager
    pool = await get_pool()
    async with pool.acquire() as conn:
        readings = await conn.fetchval("SELECT COUNT(*) FROM readings")
        alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts")
    return {"status": "ok", "readings": readings, "alerts": alerts, "ws_clients": len(manager.active)}
