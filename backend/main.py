from fastapi import FastAPI

app = FastAPI(title="MineTrack API")

@app.get("/")
async def root():
    return {"status": "MineTrack is running"}