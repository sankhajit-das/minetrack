from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Keeps track of all active browser/client WebSocket connections
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"🔌 Client connected. Total active clients: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
            logger.info(f"❌ Client disconnected. Total active clients: {len(self.active)}")

    async def broadcast(self, message: str):
        """Send a message to all connected clients. Automatically sweeps out dead connections."""
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                # Catch closed browser tabs, network drops, etc.
                dead.append(ws)
                
        # Clean up any stale connections found during the broadcast loop
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)
                
        if dead:
            logger.info(f"🧹 Cleaned up {len(dead)} dead connection(s). Total active: {len(self.active)}")

# Instantiating a module-level singleton to be imported directly across the application layers
manager = ConnectionManager()