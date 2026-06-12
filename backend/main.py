import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.database import run_schema, close_pool
from app.api.ws_routes import router as ws_router
from app.api.ws_routes import broadcast_sensor_data, listen_for_alerts
from app.api.routes import router as api_router # Added REST router import

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Warm up database schemas and connection configurations
    await run_schema()
    print("DB schema ready")
    
    # 2. Start the WebSocket broadcaster and Redis listener loops inside the Web Gateway
    app.state.tasks = [
        asyncio.create_task(broadcast_sensor_data()),
        asyncio.create_task(listen_for_alerts()),
    ]
    print("WebSocket telemetry broadcaster + Redis alert listener running.")
    
    yield
    
    # 3. Clean architecture shutdown sequence
    print("Shutting down background tasks cleanly...")
    for task in app.state.tasks:
        task.cancel()
        
    # Let tasks gracefully clear system loop bindings
    await asyncio.gather(*app.state.tasks, return_exceptions=True)
    await close_pool()
    print("All system connections flushed.")

app = FastAPI(title="MineTrack API", lifespan=lifespan)

# Allow your local React frontend application on port 5173 to bridge connection routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ws_router)
app.include_router(api_router) # Added REST router endpoints directly

@app.get("/")
async def root():
    return {"status": "MineTrack is running"}

@app.get("/health")
async def health():
    from app.db.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        readings = await conn.fetchval("SELECT COUNT(*) FROM readings")
        alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts")
        
    from app.api.ws_manager import manager
    return {
        "status": "ok",
        "readings": readings,
        "alerts": alerts,
        "ws_clients": len(manager.active)
    }

# Allow your local React frontend application on port 5173 to bridge connection routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers cleanly
app.include_router(ws_router)
app.include_router(api_router)  # This mounts /sensors, /alerts, etc. directly at the root level