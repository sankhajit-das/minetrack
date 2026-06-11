import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# global connection pool — shared across all requests
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=10
        )
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def run_schema():
    """Run schema.sql on startup to create tables if they don't exist."""
    pool = await get_pool()
    schema_path = os.path.join(
        os.path.dirname(__file__), "schema.sql"
    )
    with open(schema_path) as f:
        schema = f.read()
    
    async with pool.acquire() as conn:
        await conn.execute(schema)