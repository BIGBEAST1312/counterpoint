# Shared infrastructure | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Entry point. Run with:  uvicorn app.main:app --reload

This file only wires the features together. Each feature lives in its own folder:
  app/queue     Feature 1  Walk-up queue                    Mohit Sawant
  app/tickets   Feature 2  Ticket drafts & shift handover   Hetank Patel
  app/guides    Feature 3  Fix guides                       Priyesh Patel
  app/report    Feature 4  Weekly report & trends           Haryan Patel
  app/coverage  Feature 5  Desk coverage (+ supervisor notifications)  Aarya Patel
Shared infrastructure (no feature): app/core (settings, database, live updates), app/auth (sign-in).
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.core.database import FEATURES, import_feature, init_db
from app.core.realtime import hub

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Counterpoint API",
    description="Counterpoint: walk-up queue and desk tools for the USask IT Support desk. "
                "Each feature's endpoints are grouped under its owner.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
# Each feature is plugged in only if its folder exists, so members can merge their
# feature in any order once the shared base is on main.
for feature in FEATURES:
    module = import_feature(feature, "router")
    if module is not None:
        app.include_router(module.router)


@app.get("/api/health", tags=["Shared · Sign-in & settings"])
def health():
    return {"ok": True}


@app.websocket("/ws")
async def live_updates(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # we don't expect messages; this just keeps the socket open
    except WebSocketDisconnect:
        hub.disconnect(ws)


# Serve the frontend last so /api and /ws routes win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
