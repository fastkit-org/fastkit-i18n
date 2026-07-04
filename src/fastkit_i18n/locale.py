"""
Locale configuration - single source of truth for default/current locale.

Fully decoupled from any external config system (e.g. fastkit-core). This
module is shared by both `database.translatable` (TranslatableMixin) and
`i18n.translation` (TranslationManager), so a locale set in one place is
visible in the other — no more diverging ContextVars.

Resolution order for "what locale should I use right now":
    1. Explicit `locale=` argument passed to a call (get(), get_translation(), ...)
    2. Instance-level locale (TranslatableMixin.set_locale())
    3. Context-level locale (set_locale() below - e.g. set per-request by
       LocaleMiddleware)
    4. Model-level `__fallback_locale__` (TranslatableMixin subclasses only)
    5. App-level default (set_default_locale() below)
"""

from __future__ import annotations
from contextvars import ContextVar, Token

# ----------------------------------------------------------------------------
# App-level default locale
# ----------------------------------------------------------------------------
# Set once at startup, independent of any host framework config:
#
#   from fastkit_i18n.locale import set_default_locale
#   set_default_locale("en")
#
_default_locale: str = "en"


def set_default_locale(locale: str) -> None:
    """Set the application-wide default locale."""
    global _default_locale
    _default_locale = locale


def get_default_locale() -> str:
    """Get the application-wide default locale."""
    return _default_locale


# ----------------------------------------------------------------------------
# Context-level (per-request / per-task) locale
# ----------------------------------------------------------------------------
# Shared ContextVar so TranslatableMixin and TranslationManager always agree
# on the "current" locale. Meant to be set per request, e.g. by
# LocaleMiddleware, or manually via set_locale() below.
_current_locale: ContextVar[str | None] = ContextVar("locale", default=None)


def set_locale(locale: str) -> Token:
    """
    Set the current context-scoped locale (e.g. for the current request).

    Returns a token that can be passed to `reset_locale()` to restore the
    locale that was active before this call - useful in middleware so the
    override doesn't leak past the request it was set for.
    """
    return _current_locale.set(locale)


def reset_locale(token: Token) -> None:
    """Restore the locale that was active before the matching set_locale() call."""
    _current_locale.reset(token)


def get_locale() -> str:
    """Get the current context-scoped locale, falling back to the app default."""
    return _current_locale.get() or get_default_locale()
