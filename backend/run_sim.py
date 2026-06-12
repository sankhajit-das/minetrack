import asyncio
import logging
import asyncpg
from app.simulator.simulator import run_simulator
from app.alerts.alert_engine import get_redis

logging.basicConfig(level=logging.INFO)

async def main():
    print("Initializing standalone simulator process...")
    await get_redis()
    
    # Wait until the backend initializes the schema tables
    for attempt in range(10):
        try:
            await run_simulator()
            break
        except asyncpg.exceptions.UndefinedTableError:
            print(f"Database tables not initialized by backend yet (attempt {attempt + 1}/10). Waiting 3 seconds...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Unexpected simulator error: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())