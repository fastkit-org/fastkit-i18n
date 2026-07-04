"""
Tests for LocaleMiddleware (fastkit_translation.middleware).

Adapted from the original fastkit-core test suite for the standalone
fastkit-translation package:
- fastkit_translate -> fastkit_translation
- LocaleMiddleware is now a pure ASGI middleware (no starlette dependency),
  but it's still fully compatible with app.add_middleware() on FastAPI/
  Starlette, which is what these tests exercise end-to-end
- setup_i18n fixture is defined locally (it isn't part of the package) to
  reset the shared locale context/app default between tests
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkit_translation import LocaleMiddleware, get_locale
from fastkit_translation.locale import _current_locale, set_default_locale


@pytest.fixture
def setup_i18n():
    """Reset the shared locale context and app-wide default around each test."""
    _current_locale.set(None)
    set_default_locale('en')
    yield
    _current_locale.set(None)
    set_default_locale('en')


class TestLocaleMiddleware:
    """Test LocaleMiddleware."""

    def test_locale_from_accept_language_header(self, setup_i18n):
        """Should detect locale from Accept-Language header."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        client.get("/test", headers={"Accept-Language": "es-ES"})

        assert detected_locale == "es"

    def test_locale_from_query_parameter(self, setup_i18n):
        """Should detect locale from query parameter."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        client.get("/test?lang=fr")

        assert detected_locale == "fr"

    def test_locale_from_cookie(self, setup_i18n):
        """Should detect locale from cookie."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        client.get("/test", cookies={"locale": "de"})

        assert detected_locale == "de"

    def test_locale_priority(self, setup_i18n):
        """Should prioritize Accept-Language header over cookie."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        # Header should take precedence over cookie
        client.get(
            "/test",
            headers={"Accept-Language": "es-ES"},
            cookies={"locale": "fr"}
        )

        assert detected_locale == "es"

    def test_locale_default_fallback(self, setup_i18n):
        """Should fallback to the app-wide default locale."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        client.get("/test")

        assert detected_locale == "en"  # Default

    def test_locale_reset_after_request(self, setup_i18n):
        """Should not leak the per-request locale override past the request."""
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        @app.get("/test")
        def test_route():
            return {"locale": get_locale()}

        client = TestClient(app)

        response = client.get("/test", headers={"Accept-Language": "de-DE"})
        assert response.json()["locale"] == "de"

        # Outside of any request, the context should be back to the default -
        # the middleware's token-based reset must not leave "de" set globally.
        assert get_locale() == "en"

    def test_custom_app_default_locale(self, setup_i18n):
        """Should fall back to a custom app-wide default, not a hardcoded 'en'."""
        set_default_locale('fr')

        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        detected_locale = None

        @app.get("/test")
        def test_route():
            nonlocal detected_locale
            detected_locale = get_locale()
            return {"ok": True}

        client = TestClient(app)
        client.get("/test")

        assert detected_locale == "fr"
