import asyncio
from typing import DefaultDict
from collections import defaultdict
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id -> list of active WebSocket connections
        self._connections: DefaultDict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        await websocket.accept()
        self._connections[user_id].append(websocket)
        logger.info("WS connected: user_id=%s (total connections=%s)", user_id, len(self._connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        sockets = self._connections.get(user_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._connections.pop(user_id, None)
        logger.info("WS disconnected: user_id=%s", user_id)

    async def send_to_user(self, user_id: int, data: dict) -> None:
        sockets = list(self._connections.get(user_id, []))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(data)
            except Exception as exc:
                logger.warning("Failed to send WS message to user %s: %s", user_id, exc)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast(self, data: dict) -> None:
        all_user_ids = list(self._connections.keys())
        tasks = [self.send_to_user(uid, data) for uid in all_user_ids]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def is_connected(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def connected_user_ids(self) -> list[int]:
        return list(self._connections.keys())


manager = ConnectionManager()
