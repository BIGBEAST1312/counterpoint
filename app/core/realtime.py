# Shared infrastructure | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Live updates over WebSockets.

Design choice: the server only says WHAT changed (e.g. "queue", "status"), never the data.
Each browser then re-fetches from the normal API. That keeps one source of truth (the REST
endpoints, with their auth checks) and means the public screens never receive names.

Usage inside a route:
    background.add_task(hub.broadcast, "queue")
"""
from fastapi import WebSocket

# One topic per feature (plus notifications), so each screen reloads only what it shows.
TOPICS = {"queue", "tickets", "handover", "guides", "status", "notifications", "timeaway"}


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, topic: str) -> None:
        assert topic in TOPICS, f"Unknown topic {topic!r}; add it to TOPICS"
        for ws in list(self.clients):
            try:
                await ws.send_json({"topic": topic})
            except Exception:  # browser tab closed mid-send
                self.disconnect(ws)


hub = Hub()
