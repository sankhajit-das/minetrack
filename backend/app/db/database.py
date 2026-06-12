import os
import asyncpg
import asyncio
from dotenv import load_dotenv

load_dotenv()

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        for attempt in range(5):
            try:
                _pool = await asyncpg.create_pool(
                    dsn=os.getenv("DATABASE_URL"),
                    min_size=2,
                    max_size=10
                )
                break
            except Exception as e:
                if attempt == 4:
                    raise e
                print(f"Database not ready yet (attempt {attempt + 1}/5). Retrying in 2 seconds...")
                await asyncio.sleep(2)
                
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def run_schema():
    """Reads schema.sql and executes it to set up hypertables and seed data."""
    pool = await get_pool()
    # Find the schema.sql file relative to this database.py file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(current_dir, "schema.sql")
    
    with open(schema_path, "r") as f:
        schema_sql = f.read()
        
    async with pool.acquire() as conn:
        print("Executing schema.sql migrations...")
        await conn.execute(schema_sql)
        print("Database migration complete.")