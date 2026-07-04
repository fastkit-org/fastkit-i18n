from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..locale import set_locale, reset_locale, get_default_locale

class LocaleMiddleware(BaseHTTPMiddleware):
    """
    Set locale from request headers, query params, or cookies.

    Priority:
    1. Accept-Language header
    2. ?lang= query parameter
    3. locale cookie
    4. App-wide default (fastkit_translation.locale.set_default_locale)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get locale from header, query param, or cookie
        locale = (
                request.headers.get('Accept-Language', '')[:2]
                or request.query_params.get('lang')
                or request.cookies.get('locale')
                or get_default_locale()
        )

        # Use a token so the override is scoped to this request only - it
        # won't leak into background tasks or get reused by another request
        # sharing the same context.
        token = set_locale(locale)
        try:
            response = await call_next(request)
        finally:
            reset_locale(token)

        return response