from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class LocaleMiddleware(BaseHTTPMiddleware):
    """
    Set locale from request headers, query params, or cookies.

    Priority:
    1. Accept-Language header
    2. ?lang= query parameter
    3. locale cookie
    4. Default: 'en'
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from ..locale import set_locale, get_default_locale
        # Get locale from header, query param, or cookie
        locale = (
                request.headers.get('Accept-Language', '')[:2]
                or request.query_params.get('lang')
                or request.cookies.get('locale')
                or get_default_locale()
        )


        set_locale(locale)

        response = await call_next(request)
        return response