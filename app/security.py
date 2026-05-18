from __future__ import annotations

import os
import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


def dashboard_auth_enabled() -> bool:
    return bool(os.getenv("DASHBOARD_USERNAME") and os.getenv("DASHBOARD_PASSWORD"))


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """Optional HTTP Basic Auth for dashboard + API (set DASHBOARD_USERNAME/PASSWORD)."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.username = os.getenv("DASHBOARD_USERNAME", "")
        self.password = os.getenv("DASHBOARD_PASSWORD", "")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.username or not self.password:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return self._unauthorized()

        import base64

        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            user, _, pwd = decoded.partition(":")
        except Exception:
            return self._unauthorized()

        if not (
            secrets.compare_digest(user, self.username)
            and secrets.compare_digest(pwd, self.password)
        ):
            return self._unauthorized()

        return await call_next(request)

    @staticmethod
    def _unauthorized() -> Response:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Trading Dashboard"'},
            content="Unauthorized",
        )
