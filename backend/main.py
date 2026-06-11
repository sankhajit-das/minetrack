from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.database import run_schema, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs on startup: Initialize the DB and inject tables/seed records
    await run_schema()
    print("DB schema ready")
    
    yield
    
    # Runs on shutdown: Clean up connection links cleanly
    await close_pool()

app = FastAPI(title="MineTrack API", lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "MineTrack is running"}

@app.get("/health")
async def health():
    from app.db.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM sensors")
    return {"status": "ok", "sensors_in_db": result}