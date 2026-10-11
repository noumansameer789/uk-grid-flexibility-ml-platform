"""Per-process portfolio API limits. A multi-replica service needs a shared gateway."""

import asyncio
import math
import time
from collections import deque

from starlette.responses import JSONResponse


class RequestLimits:
    def __init__(self, app, max_body_bytes=16384, requests_per_minute=120):
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.requests_per_minute = requests_per_minute
        self.arrivals = deque()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        now = time.monotonic()
        while self.arrivals and self.arrivals[0] <= now - 60:
            self.arrivals.popleft()
        if len(self.arrivals) >= self.requests_per_minute:
            retry = max(1, math.ceil(60 - (now - self.arrivals[0])))
            response = JSONResponse(
                {"detail": "API capacity reached; retry shortly."}, 429, headers={"Retry-After": str(retry)}
            )
            return await response(scope, receive, send)
        self.arrivals.append(now)
        body = bytearray()
        deadline = time.monotonic() + 5
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - time.monotonic()))
            except TimeoutError:
                return await JSONResponse({"detail": "Request body timed out"}, 408)(scope, receive, send)
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_bytes:
                return await JSONResponse(
                    {"detail": f"Request body exceeds {self.max_body_bytes} bytes"}, 413
                )(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay_body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay_body, send)
