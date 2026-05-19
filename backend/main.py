import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

import config
from database import init_db
from auth import decode_jwt, router as auth_router
from routes.raids import router as raids_router
from routes.users import router as users_router
from routes.grind import router as grind_router
from services.ws_manager import manager as ws_manager
from services.verifier import verification_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initialising database...")
    init_db()

    logger.info("Starting APScheduler...")
    scheduler.add_job(
        verification_job,
        "interval",
        seconds=30,
        id="verification_job",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("APScheduler started. Verification job running every 30s.")

    yield

    # Shutdown
    logger.info("Shutting down APScheduler...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="raid-fun API",
    description="Social raiding platform for the IDOL64 web3/crypto community",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# FRONTEND_URL can be a comma-separated list, e.g. for allowing both local dev and prod
_allowed_origins = [o.strip() for o in config.FRONTEND_URL.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(raids_router)
app.include_router(users_router)
app.include_router(grind_router)


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "mock_mode": config.MOCK_MODE}


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Authenticated WebSocket endpoint.
    Connect with: ws://localhost:8000/ws?token=<jwt>
    """
    # Validate JWT before accepting connection
    try:
        user_id = decode_jwt(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await ws_manager.connect(websocket, user_id)
    logger.info("WebSocket authenticated: user_id=%s", user_id)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "message": "Connected to raid-fun real-time feed",
        })

        # Keep connection alive — listen for any client messages (ping/pong)
        while True:
            data = await websocket.receive_text()
            # Handle client-side ping
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user_id=%s", user_id)
    except Exception as exc:
        logger.warning("WebSocket error for user_id=%s: %s", user_id, exc)
    finally:
        ws_manager.disconnect(websocket, user_id)


# ── Frontend static files ─────────────────────────────────────────────────────
# Serve the frontend SPA. Must come AFTER all API routes so they take priority.
_frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

if os.path.isdir(_frontend_dir):
    # Serve individual asset files (style.css, app.js, sw.js, manifest.json …)
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found at %s — skipping static mount", _frontend_dir)
