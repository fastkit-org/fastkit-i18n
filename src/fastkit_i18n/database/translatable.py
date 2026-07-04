"""
TranslatableMixin - Transparent multi-language field support.

Automatically handles translation storage and retrieval with zero boilerplate.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
import json

try:
    from sqlalchemy import event, exc
except ImportError as err:  # pragma: no cover
    raise ImportError(
        "fastkit_i18n.database.translatable requires SQLAlchemy. "
        "Install it with: pip install fastkit-i18n[sqlalchemy]"
    ) from err

from fastkit_i18n.locale import _current_locale, get_default_locale

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TranslatableMixin:
    """
    Automatic multi-language support with zero boilerplate.

    Features:
    - Transparent get/set (works like normal strings)
    - Context-aware locale (from request or manual)
    - Partial updates (update one language, keep others)
    - Fallback to default locale
    - Stores as JSON in database

    Example:
        from sqlalchemy import JSON

        class Article(Base, TranslatableMixin, TimestampMixin):
            __tablename__ = 'articles'
            __translatable__ = ['title', 'content']
            __fallback_locale__ = 'en'

            # Must explicitly define as JSON columns
            title: Mapped[dict] = mapped_column(JSON)
            content: Mapped[dict] = mapped_column(JSON)

            # Non-translatable fields work normally
            author: Mapped[str]

        # Usage - transparent string interface
        article = Article()
        article.title = "Hello World"  # Saves to current locale

        article.set_locale('es')
        article.title = "Hola Mundo"  # Updates Spanish only

        article.set_locale('en')
        print(article.title)  # "Hello World"

        # Get all translations
        print(article.get_translations('title'))
        # {'en': 'Hello World', 'es': 'Hola Mundo'}

    Note:
        Fields must be defined as JSON columns:
        `field: Mapped[dict] = mapped_column(JSON)`
    """

    # Configure in your model
    __translatable__: list[str] = []
    __fallback_locale__: str = None  # If unset, falls back to the app-wide
                                      # default (fastkit_i18n.locale.set_default_locale)

    @property
    def _fallback_locale(self) -> str:
        """Model-level fallback locale, or the app-wide default if unset."""
        if self.__fallback_locale__ is None:
            return get_default_locale()
        return self.__fallback_locale__

    def get_locale(self) -> str:
        """Get current locale for this instance."""
        # Instance-specific locale
        if hasattr(self, '_instance_locale'):
            return self._instance_locale

        # Global locale
        global_locale = _current_locale.get()
        if global_locale:
            return global_locale

        # Fallback to default
        return self._fallback_locale

    def set_locale(self, locale: str) -> 'TranslatableMixin':
        """Set locale for this instance. Returns self for chaining."""
        self._instance_locale = locale
        return self

    def __init_subclass__(cls, **kwargs) -> None:
        """
        Fail fast if another base class wins the MRO for __setattr__ or
        __getattribute__.

        TranslatableMixin does not cooperate via super() in these dunders -
        it must be the one Python resolves to, or transparent field access
        breaks *silently*: e.g. mixed with SQLModel/pydantic in the wrong
        order, writes go through the other class's __setattr__ (bypassing
        the translation dict) while reads still go through ours (finding
        nothing), so a field looks like it "lost" its value instead of
        raising an error.

        Fix: put TranslatableMixin first in the base class list, e.g.
            class Article(TranslatableMixin, SQLModel, table=True): ...
            class Article(TranslatableMixin, Base): ...
        """
        super().__init_subclass__(**kwargs)

        conflicts = []
        if cls.__setattr__ is not TranslatableMixin.__setattr__:
            conflicts.append(('__setattr__', cls.__setattr__.__qualname__))
        if cls.__getattribute__ is not TranslatableMixin.__getattribute__:
            conflicts.append(('__getattribute__', cls.__getattribute__.__qualname__))

        if conflicts:
            details = '; '.join(f'{name} resolves to {owner}' for name, owner in conflicts)
            raise TypeError(
                f"{cls.__name__}: another base class overrides {details}, which "
                f"would silently break TranslatableMixin's transparent field access "
                f"(translations could be written but never read back, or vice versa, "
                f"with no error raised). Put TranslatableMixin FIRST in the base "
                f"class list, e.g.:\n"
                f"    class {cls.__name__}(TranslatableMixin, <YourOtherBase>, ...): ..."
            )

        # Register the (de)serialization hooks directly on this concrete
        # class, rather than once on the bare mixin at module import time.
        #
        # A module-level `event.listens_for(TranslatableMixin, 'load',
        # propagate=True)` only works if some other declarative base/mapped
        # class has already been touched earlier in the *process* - without
        # that, SQLAlchemy doesn't yet recognize a plain, never-mapped class
        # as a valid propagate target and raises InvalidRequestError. That
        # makes behavior depend on unrelated import order elsewhere in the
        # app, which is exactly the kind of implicit coupling this package
        # is trying to avoid.
        #
        # Registering per-concrete-class here instead - after `super().
        # __init_subclass__()` above has already run the real declarative/
        # SQLModel mapping - sidesteps that entirely, since `cls` is
        # guaranteed to already be mapped by this point (both here and for
        # any further subclass of `cls`, since __init_subclass__ re-fires
        # for each level). Abstract/never-mapped intermediate classes just
        # skip registration quietly and get it at whichever concrete
        # subclass actually ends up mapped.
        try:
            event.listen(cls, 'load', deserialize_translations)
            event.listen(cls, 'before_insert', serialize_translations)
            event.listen(cls, 'before_update', serialize_translations)
        except exc.InvalidRequestError:
            pass

    @classmethod
    def set_global_locale(cls, locale: str) -> None:
        """Set global locale (affects all instances in current context)."""
        _current_locale.set(locale)

    @classmethod
    def get_global_locale(cls) -> str:
        """Get current global locale."""
        return _current_locale.get() or get_default_locale()

    def get_translations(self, field: str) -> dict[str, str]:
        """
        Get all translations for a field.

        Args:
            field: Field name

        Returns:
            Dict mapping locale codes to translated values
            Example: {'en': 'Hello', 'es': 'Hola', 'fr': 'Bonjour'}

        Raises:
            ValueError: If field is not translatable
        """
        if field not in self.__translatable__:
            raise ValueError(f"Field '{field}' is not translatable")

        storage_name = f'_translatable_{field}'
        translations = getattr(self, storage_name, None)

        if translations is None:
            return {}

        return translations.copy()

    def set_translation(
            self,
            field: str,
            value: str,
            locale: str = None
    ) -> 'TranslatableMixin':
        """
        Set translation for specific locale explicitly.

        Args:
            field: Field name
            value: Translated value
            locale: Locale code (e.g., 'en', 'es'). If None, uses current locale.

        Returns:
            Self for chaining

        Raises:
            ValueError: If field is not translatable
        """
        if field not in self.__translatable__:
            raise ValueError(f"Field '{field}' is not translatable")

        if locale is None:
            locale = self.get_locale()

        storage_name = f'_translatable_{field}'
        translations = getattr(self, storage_name, None)
        if translations is None:
            translations = {}
            setattr(self, storage_name, translations)

        translations[locale] = value

        # Mark as modified for SQLAlchemy only if object is persistent
        from sqlalchemy import inspect as sa_inspect

        try:
            inspector = sa_inspect(self)
            # Only flag modified if object is persistent (has been committed)
            # or pending (added to session but not committed)
            if inspector.persistent or inspector.pending:
                from sqlalchemy.orm import attributes
                attributes.flag_modified(self, field)
        except Exception:
            # Object not yet tracked by SQLAlchemy, skip flag_modified
            pass

        return self

    def get_translation(
            self,
            field: str,
            locale: str = None,
            fallback: bool = True
    ) -> str | None:
        """
        Get translation for specific locale explicitly.

        Args:
            field: Field name
            locale: Locale code. If None, uses current locale.
            fallback: If True, fallback to default locale if not found

        Returns:
            Translated value or None

        Raises:
            ValueError: If field is not translatable
        """
        if field not in self.__translatable__:
            raise ValueError(f"Field '{field}' is not translatable")

        if locale is None:
            locale = self.get_locale()

        translations = self.get_translations(field)

        # Try requested locale
        if locale in translations:
            return translations[locale]

        # Fallback to default locale
        if fallback and locale != self._fallback_locale:
            return translations.get(self._fallback_locale)

        return None

    def has_translation(self, field: str, locale: str = None) -> bool:
        """
        Check if translation exists for field in specific locale.

        Args:
            field: Field name
            locale: Locale code. If None, uses current locale.

        Returns:
            True if translation exists, False otherwise
        """
        if field not in self.__translatable__:
            return False

        if locale is None:
            locale = self.get_locale()

        translations = self.get_translations(field)
        return locale in translations and bool(translations[locale])

    def validate_translations(
            self,
            required_locales: list[str] = None
    ) -> dict[str, list[str]]:
        """
        Validate that all translatable fields have translations.

        Args:
            required_locales: List of locales that must have translations

        Returns:
            Dict of missing translations: {'field': ['locale1', 'locale2']}
        """
        required_locales = required_locales or [self._fallback_locale]
        missing = {}

        for field in self.__translatable__:
            missing_locales = []
            for locale in required_locales:
                if not self.has_translation(field, locale):
                    missing_locales.append(locale)

            if missing_locales:
                missing[field] = missing_locales

        return missing

    # ========================================================================
    # MAGIC METHODS - Make fields transparent
    # ========================================================================

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Intercept attribute setting for translatable fields.

        Converts: article.title = "Hello"
        Into: article._translatable_title = {"en": "Hello"}
        """
        # Skip internal attributes and non-translatable fields
        if (name.startswith('_') or
                not hasattr(self, '__translatable__') or
                name not in self.__translatable__):
            # Normal attribute setting
            object.__setattr__(self, name, value)
            return

        # This is a translatable field - store as translation
        self.set_translation(name, value)

    def __getattribute__(self, name: str) -> Any:
        """
        Intercept attribute access for translatable fields.

        Converts: article.title
        Into: article._translatable_title["en"]
        """
        # Get the __translatable__ list first (avoid recursion)
        try:
            translatable = object.__getattribute__(self, '__translatable__')
        except AttributeError:
            translatable = []

        # If this is a translatable field, return translated value
        if name in translatable:
            # Use get_translation method to get the value
            return object.__getattribute__(self, 'get_translation')(name)

        # Normal attribute access
        return object.__getattribute__(self, name)


# ============================================================================
# SQLAlchemy Event Listener Functions
#
# These are registered per-concrete-class from TranslatableMixin's
# __init_subclass__ above, not at module level - see the comment there for
# why.
# ============================================================================
def deserialize_translations(target, context):
    """
    After loading from DB, parse JSON into internal storage.

    Converts database JSON to internal _translatable_* attributes.
    """
    if not hasattr(target, '__translatable__'):
        return

    for field in target.__translatable__:
        storage_name = f'_translatable_{field}'

        # Get raw value from database column
        # Use object.__getattribute__ to bypass our custom __getattribute__
        try:
            raw_value = object.__getattribute__(target, field)
        except AttributeError:
            continue

        if raw_value is None:
            # No translations stored
            object.__setattr__(target, storage_name, {})
            continue

        if isinstance(raw_value, dict):
            # Already parsed by SQLAlchemy JSON type
            object.__setattr__(target, storage_name, raw_value)
        elif isinstance(raw_value, str):
            # Need to parse JSON string (shouldn't happen with JSON column type)
            try:
                translations = json.loads(raw_value)
                object.__setattr__(target, storage_name, translations)
            except json.JSONDecodeError:
                # Invalid JSON, treat as single translation
                fallback_locale = getattr(target, '_fallback_locale', 'en')
                object.__setattr__(target, storage_name, {
                    fallback_locale: raw_value
                })
        else:
            # Unknown type
            object.__setattr__(target, storage_name, {})


def serialize_translations(mapper, connection, target):
    """
    Before saving to DB, convert internal storage to JSON.

    Converts _translatable_* attributes to database JSON columns.
    """
    if not hasattr(target, '__translatable__'):
        return

    for field in target.__translatable__:
        storage_name = f'_translatable_{field}'

        # Get translations from internal storage
        translations = object.__getattribute__(target, storage_name) if hasattr(target, storage_name) else {}

        # Set the database column value
        # SQLAlchemy will handle JSON serialization
        object.__setattr__(target, field, translations if translations else None)


def set_locale_from_request(locale: str) -> None:
    """
    Helper to set locale from FastAPI request.

    Usage in FastAPI:
        @app.middleware("http")
        async def locale_middleware(request: Request, call_next):
            locale = request.headers.get('Accept-Language', 'en')[:2]
            set_locale_from_request(locale)
            response = await call_next(request)
            return response
    """
    TranslatableMixin.set_global_locale(locale)