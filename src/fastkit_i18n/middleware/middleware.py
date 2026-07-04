"""
LocaleMiddleware - pure ASGI middleware, no framework dependency.

Speaks only the ASGI protocol (scope/receive/send), so it works with
FastAPI, Starlette, Litestar, or any other ASGI framework/raw ASGI app -
no `starlette` (or any other) dependency required.
"""

from __future__ import annotations
from urllib.parse import parse_qs

from ..locale import set_locale, reset_locale, get_default_locale


class LocaleMiddleware:
    """
    Set locale from request headers, query params, or cookies.

    Priority:
    1. Accept-Language header
    2. ?lang= query parameter
    3. locale cookie
    4. App-wide default (fastkit_i18n.locale.set_default_locale)

    Usage (any ASGI app, e.g. FastAPI/Starlette):
        from fastkit_i18n.middleware import LocaleMiddleware

        app.add_middleware(LocaleMiddleware)

    Or wrap directly for raw ASGI apps:
        app = LocaleMiddleware(app)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            # Not an HTTP request (e.g. lifespan, websocket) - pass through.
            await self.app(scope, receive, send)
            return

        locale = (
                self._get_header(scope, b"accept-language")[:2]
                or self._get_query_param(scope, "lang")
                or self._get_cookie(scope, "locale")
                or get_default_locale()
        )

        # Use a token so the override is scoped to this request only - it
        # won't leak into background tasks or get reused by another request
        # sharing the same context.
        token = set_locale(locale)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_locale(token)

    @staticmethod
    def _get_header(scope, name: bytes) -> str:
        """Read a single header value from the ASGI scope (lowercase byte keys)."""
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return ""

    @staticmethod
    def _get_query_param(scope, name: str) -> str | None:
        """Read a single query param from the ASGI scope's query_string."""
        query_string = scope.get("query_string", b"").decode("latin-1")
        if not query_string:
            return None
        params = parse_qs(query_string)
        values = params.get(name)
        return values[0] if values else None

    @staticmethod
    def _get_cookie(scope, name: str) -> str | None:
        """Read a single cookie value from the ASGI scope's Cookie header."""
        cookie_header = LocaleMiddleware._get_header(scope, b"cookie")
        if not cookie_header:
            return None
        for part in cookie_header.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                if key == name:
                    return value
        return None
