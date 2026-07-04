"""
Tests for TranslatableMixin (fastkit_i18n.database.translatable).

Adapted from the original fastkit-core test suite for the standalone
fastkit-i18n package:
- fastkit_core.database.Base/IntIdMixin -> local DeclarativeBase + explicit
  id columns (fastkit-i18n has no ORM base class of its own, only
  the mixin)
- fastkit_core.i18n -> fastkit_i18n.locale
- Base.to_dict() integration tests removed - serialization/to_dict is not
  part of this package's scope
"""

import pytest
from sqlalchemy import create_engine, String, JSON, Integer
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, DeclarativeBase

from fastkit_i18n import TranslatableMixin
from fastkit_i18n.locale import set_locale, get_locale


# ============================================================================
# Test Models
# ============================================================================

class Base(DeclarativeBase):
    pass


class Article(TranslatableMixin, Base):
    """Article with translatable fields."""
    __tablename__ = 'articles'
    __translatable__ = ['title', 'content']

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[dict] = mapped_column(JSON)
    content: Mapped[dict] = mapped_column(JSON)
    author: Mapped[str] = mapped_column(String(100))  # Non-translatable


class Product(TranslatableMixin, Base):
    """Product with custom fallback locale."""
    __tablename__ = 'products'
    __translatable__ = ['name', 'description']
    __fallback_locale__ = 'es'  # Custom fallback

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON)
    description: Mapped[dict] = mapped_column(JSON)
    price: Mapped[int] = mapped_column(Integer)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def engine():
    """Create in-memory SQLite engine."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def reset_locale():
    """Reset locale before and after each test."""
    set_locale('en')
    yield
    set_locale('en')


# ============================================================================
# Test Basic Get/Set Operations
# ============================================================================

class TestBasicGetSet:
    """Test basic get/set operations."""

    def test_set_single_locale(self, session):
        """Should set translation for current locale."""
        article = Article(author="John")
        session.add(article)  # Add to session FIRST
        session.flush()  # Ensure it's tracked

        article.title = "Hello World"

        assert article.title == "Hello World"

    def test_set_multiple_locales(self, session):
        """Should set translations for multiple locales."""
        article = Article(author="John")
        session.add(article)  # Add to session FIRST
        session.flush()

        set_locale('en')
        article.title = "Hello World"

        set_locale('es')
        article.title = "Hola Mundo"

        set_locale('fr')
        article.title = "Bonjour le Monde"

        # Verify all are stored
        set_locale('en')
        assert article.title == "Hello World"

        set_locale('es')
        assert article.title == "Hola Mundo"

        set_locale('fr')
        assert article.title == "Bonjour le Monde"

    def test_set_multiple_fields(self, session):
        """Should handle multiple translatable fields."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        article.content = "Content in English"

        assert article.title == "Hello"
        assert article.content == "Content in English"

    def test_get_fallback_translation(self, session):
        """Should fall back to another locale's value if current one is unset."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        set_locale('fr')
        # No French translation set - falls back to the model's fallback locale (en)
        assert article.title == "Hello"

    def test_non_translatable_field_works_normally(self, session):
        """Should handle non-translatable fields normally."""
        article = Article(author="John")
        article.title = "Test"

        # Author is not translatable
        assert article.author == "John"

        # Should work the same regardless of locale
        set_locale('es')
        assert article.author == "John"


# ============================================================================
# Test Locale Management
# ============================================================================

class TestLocaleManagement:
    """Test locale management."""

    def test_get_locale_default(self, session):
        """Should return default locale."""
        article = Article(author="John")

        locale = article.get_locale()

        assert locale == 'en'

    def test_set_locale_instance(self, session):
        """Should set instance-specific locale."""
        article = Article(author="John")

        article.set_locale('es')

        assert article.get_locale() == 'es'

    def test_set_locale_chainable(self, session):
        """Should return self for chaining."""
        article = Article(author="John")

        result = article.set_locale('es')

        assert result is article

    def test_instance_locale_overrides_global(self, session):
        """Should prioritize instance locale over global."""
        article = Article(author="John")

        # Set global (context) locale
        TranslatableMixin.set_global_locale('en')

        # Set instance locale
        article.set_locale('es')

        assert article.get_locale() == 'es'

    def test_global_locale_affects_all_instances(self, session):
        """Should affect all instances without instance locale."""
        article1 = Article(author="John")
        article2 = Article(author="Jane")

        TranslatableMixin.set_global_locale('es')

        assert article1.get_locale() == 'es'
        assert article2.get_locale() == 'es'

    def test_get_global_locale(self, session):
        """Should get current global locale."""
        TranslatableMixin.set_global_locale('fr')

        assert TranslatableMixin.get_global_locale() == 'fr'


# ============================================================================
# Test Translation Methods
# ============================================================================

class TestTranslationMethods:
    """Test translation helper methods."""

    def test_get_translations(self, session):
        """Should get all translations for a field."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        set_locale('es')
        article.title = "Hola"

        translations = article.get_translations('title')

        assert translations == {'en': 'Hello', 'es': 'Hola'}

    def test_get_translations_empty(self, session):
        """Should return empty dict for field with no translations."""
        article = Article(author="John")

        translations = article.get_translations('title')

        assert translations == {}

    def test_get_translations_invalid_field(self, session):
        """Should raise error for non-translatable field."""
        article = Article(author="John")

        with pytest.raises(ValueError) as exc_info:
            article.get_translations('author')

        assert 'not translatable' in str(exc_info.value).lower()

    def test_set_translation_explicit(self, session):
        """Should set translation for specific locale."""
        article = Article(author="John")

        article.set_translation('title', 'Bonjour', locale='fr')

        set_locale('fr')
        assert article.title == "Bonjour"

    def test_set_translation_current_locale(self, session):
        """Should use current locale if not specified."""
        article = Article(author="John")

        set_locale('es')
        article.set_translation('title', 'Hola')

        assert article.title == "Hola"

    def test_set_translation_chainable(self, session):
        """Should return self for chaining."""
        article = Article(author="John")

        result = article.set_translation('title', 'Hello')

        assert result is article

    def test_set_translation_invalid_field(self, session):
        """Should raise error for non-translatable field."""
        article = Article(author="John")

        with pytest.raises(ValueError) as exc_info:
            article.set_translation('author', 'John', locale='es')

        assert 'not translatable' in str(exc_info.value).lower()

    def test_get_translation_explicit(self, session):
        """Should get translation for specific locale."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        translation = article.get_translation('title', locale='en')

        assert translation == "Hello"

    def test_get_translation_with_fallback(self, session):
        """Should fallback to default locale."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        # Request French (doesn't exist), should fallback to English
        translation = article.get_translation('title', locale='fr', fallback=True)

        assert translation == "Hello"

    def test_get_translation_without_fallback(self, session):
        """Should not fallback when disabled."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        translation = article.get_translation('title', locale='fr', fallback=False)

        assert translation is None

    def test_has_translation(self, session):
        """Should check if translation exists."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        assert article.has_translation('title', locale='en') is True
        assert article.has_translation('title', locale='es') is False

    def test_has_translation_current_locale(self, session):
        """Should check current locale if not specified."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        assert article.has_translation('title') is True

        set_locale('es')
        assert article.has_translation('title') is False

    def test_has_translation_invalid_field(self, session):
        """Should return False for non-translatable field."""
        article = Article(author="John")

        assert article.has_translation('author') is False


# ============================================================================
# Test Validation
# ============================================================================

class TestValidation:
    """Test translation validation."""

    def test_validate_translations_all_present(self, session):
        """Should validate when all required translations present."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        article.content = "Content"

        missing = article.validate_translations(required_locales=['en'])

        assert missing == {}

    def test_validate_translations_missing(self, session):
        """Should detect missing translations."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        # content not set

        missing = article.validate_translations(required_locales=['en'])

        assert 'content' in missing
        assert 'en' in missing['content']

    def test_validate_translations_multiple_locales(self, session):
        """Should validate across multiple locales."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        article.content = "Content"

        set_locale('es')
        article.title = "Hola"
        # content not set in Spanish

        missing = article.validate_translations(required_locales=['en', 'es'])

        assert 'content' in missing
        assert 'es' in missing['content']
        assert 'en' not in missing.get('content', [])

    def test_validate_translations_default_locale(self, session):
        """Should default to fallback locale."""
        article = Article(author="John")

        missing = article.validate_translations()

        # Should check default locale (en)
        assert 'title' in missing
        assert 'content' in missing


# ============================================================================
# Test Database Persistence
# ============================================================================

class TestDatabasePersistence:
    """Test database save and load."""

    def test_save_and_load_single_locale(self, session):
        """Should persist single locale to database."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello World"
        article.content = "English content"

        session.add(article)
        session.commit()

        # Reload from database
        session.expire_all()
        loaded = session.query(Article).first()

        set_locale('en')
        assert loaded.title == "Hello World"
        assert loaded.content == "English content"

    def test_save_and_load_multiple_locales(self, session):
        """Should persist multiple locales."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        article.content = "English"

        set_locale('es')
        article.title = "Hola"
        article.content = "Español"

        session.add(article)
        session.commit()

        # Reload
        session.expire_all()
        loaded = session.query(Article).first()

        set_locale('en')
        assert loaded.title == "Hello"

        set_locale('es')
        assert loaded.title == "Hola"

    def test_update_translation(self, session):
        """Should update existing translation."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Original"

        session.add(article)
        session.commit()

        # Update
        article.title = "Updated"
        session.commit()

        # Reload
        session.expire_all()
        loaded = session.query(Article).first()

        assert loaded.title == "Updated"

    def test_add_new_locale(self, session):
        """Should add new locale to existing record."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        session.add(article)
        session.commit()

        # Add Spanish
        set_locale('es')
        article.title = "Hola"
        session.commit()

        # Reload
        session.expire_all()
        loaded = session.query(Article).first()

        set_locale('en')
        assert loaded.title == "Hello"

        set_locale('es')
        assert loaded.title == "Hola"

    def test_partial_update(self, session):
        """Should update one field without affecting others."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"
        article.content = "Content"

        session.add(article)
        session.commit()

        # Update only title
        article.title = "Updated Title"
        session.commit()

        session.expire_all()
        loaded = session.query(Article).first()

        assert loaded.title == "Updated Title"
        assert loaded.content == "Content"  # Unchanged


# ============================================================================
# Test Fallback Behavior
# ============================================================================

class TestFallbackBehavior:
    """Test locale fallback behavior."""

    def test_fallback_to_default_locale(self, session):
        """Should fallback to default locale."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        # Request non-existent locale
        set_locale('fr')
        translation = article.get_translation('title', fallback=True)

        assert translation == "Hello"

    def test_custom_fallback_locale(self, session):
        """Should use custom fallback locale."""
        product = Product(price=100)

        # Product has __fallback_locale__ = 'es'
        product.set_locale('es')
        product.name = "Producto"

        # Request non-existent locale, should fallback to es
        translation = product.get_translation('name', locale='fr', fallback=True)

        assert translation == "Producto"

    def test_no_fallback_returns_none(self, session):
        """Should return None when fallback disabled."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Hello"

        translation = article.get_translation('title', locale='fr', fallback=False)

        assert translation is None


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_string_translation(self, session):
        """Should handle empty strings."""
        article = Article(author="John")

        article.title = ""

        assert article.title == ""

    def test_none_translation(self, session):
        """Should handle None values."""
        article = Article(author="John")

        article.title = None

        assert article.title is None

    def test_special_characters(self, session):
        """Should handle special characters."""
        article = Article(author="John")

        article.title = "Hello! @#$%^&*() 你好 مرحبا"

        assert article.title == "Hello! @#$%^&*() 你好 مرحبا"

    def test_very_long_text(self, session):
        """Should handle very long text."""
        article = Article(author="John")

        long_text = "A" * 10000
        article.content = long_text

        assert len(article.content) == 10000

    def test_unicode_in_locale_code(self, session):
        """Should handle various locale codes."""
        article = Article(author="John")

        article.set_locale('zh-CN')
        article.title = "你好"

        assert article.get_locale() == 'zh-CN'
        assert article.title == "你好"

    def test_overwrite_existing_translation(self, session):
        """Should overwrite existing translation."""
        article = Article(author="John")

        set_locale('en')
        article.title = "Original"

        article.title = "Updated"

        assert article.title == "Updated"

    def test_multiple_instances_independent(self, session):
        """Should maintain independent translations per instance."""
        article1 = Article(author="John")
        article2 = Article(author="Jane")

        set_locale('en')
        article1.title = "Article 1"
        article2.title = "Article 2"

        assert article1.title == "Article 1"
        assert article2.title == "Article 2"

    def test_empty_translatable_list(self, session):
        """Should handle model with no translatable fields."""

        class SimpleModel(TranslatableMixin, Base):
            __tablename__ = 'simple_models'
            __translatable__ = []  # No translatable fields

            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(100))

        Base.metadata.create_all(session.bind)

        model = SimpleModel(name="Test")

        # Should work normally
        assert model.name == "Test"


# ============================================================================
# Test Integration with the shared locale module
# ============================================================================

class TestLocaleModuleIntegration:
    """Test integration with fastkit_i18n.locale."""

    def test_uses_shared_locale_context(self, session):
        """Should use locale from fastkit_i18n.locale."""
        article = Article(author="John")

        # Set via the shared locale module
        set_locale('es')

        article.title = "Hola"

        # Should use the same context
        assert article.get_locale() == 'es'
        assert article.title == "Hola"

    def test_locale_context_shared(self, session):
        """Should share locale context between TranslatableMixin and the locale module."""
        # Set global locale via TranslatableMixin
        TranslatableMixin.set_global_locale('fr')

        # fastkit_i18n.locale should see the same locale
        # (they share the same _current_locale ContextVar)
        assert get_locale() == 'fr'

        article = Article(author="John")
        assert article.get_locale() == 'fr'


# ============================================================================
# Test Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_cms_article_workflow(self, session):
        """Should handle typical CMS workflow."""
        # Create article in English
        article = Article(author="John")

        set_locale('en')
        article.title = "Getting Started with FastAPI"
        article.content = "FastAPI is a modern web framework..."

        session.add(article)
        session.commit()

        # Later, add Spanish translation
        set_locale('es')
        article.title = "Comenzando con FastAPI"
        article.content = "FastAPI es un framework web moderno..."
        session.commit()

        # Reader gets the appropriate language
        set_locale('en')
        assert article.title == "Getting Started with FastAPI"

        set_locale('es')
        assert article.title == "Comenzando con FastAPI"

    def test_ecommerce_product_catalog(self, session):
        """Should handle e-commerce product translations."""
        product = Product(price=2999)

        # English
        product.set_locale('en')
        product.name = "Laptop"
        product.description = "High-performance laptop"

        # Spanish (fallback locale for this model)
        product.set_locale('es')
        product.name = "Portátil"
        product.description = "Portátil de alto rendimiento"

        # French
        product.set_locale('fr')
        product.name = "Ordinateur portable"
        product.description = "Ordinateur portable haute performance"

        session.add(product)
        session.commit()

        # Verify all translations
        assert product.get_translation('name', 'en') == "Laptop"
        assert product.get_translation('name', 'es') == "Portátil"
        assert product.get_translation('name', 'fr') == "Ordinateur portable"

    def test_partial_translation_coverage(self, session):
        """Should handle partial translation coverage gracefully."""
        article = Article(author="John")

        # Full English
        set_locale('en')
        article.title = "Article Title"
        article.content = "Full content in English"

        # Only title in Spanish
        set_locale('es')
        article.title = "Título del artículo"
        # content not translated

        session.add(article)
        session.commit()

        # Spanish: has title, should fallback for content
        assert article.get_translation('title', 'es') == "Título del artículo"
        assert article.get_translation('content', 'es', fallback=True) == "Full content in English"


# ============================================================================
# Test Coverage Gaps
#
# Added after reviewing `pytest --cov` output: each of these exercises a
# branch that was otherwise never hit by the tests above.
# ============================================================================

class TestCoverageGaps:
    """Targeted tests for branches missed by the rest of the suite."""

    def test_get_locale_falls_back_to_model_default_with_no_context_set(self, session):
        """
        get_locale() should fall back to the model's _fallback_locale (which
        itself falls back to the app-wide default) when there is truly no
        instance locale AND no context locale set at all - not just when the
        context happens to be 'en' already (the autouse fixture normally
        leaves it set, masking this branch).
        """
        from fastkit_i18n.locale import _current_locale

        article = Article(author="John")
        token = _current_locale.set(None)
        try:
            assert article.get_locale() == 'en'  # app-wide default
        finally:
            _current_locale.reset(token)

    def test_getattribute_conflict_detected_independently_of_setattr(self, session):
        """
        The MRO guard should catch a __getattribute__-only conflict too, not
        just the __setattr__ conflict exercised by the SQLModel test - these
        are checked and reported independently.
        """
        class OverridesGetattributeOnly:
            def __getattribute__(self, name):
                return object.__getattribute__(self, name)

        with pytest.raises(TypeError, match="__getattribute__"):
            class Weird(OverridesGetattributeOnly, TranslatableMixin, Base):
                __tablename__ = 'weird_getattribute_conflict'
                __translatable__ = ['title']

                id: Mapped[int] = mapped_column(Integer, primary_key=True)
                title: Mapped[dict] = mapped_column(JSON)

    def test_works_standalone_without_any_orm_base(self):
        """
        TranslatableMixin should work as a plain in-memory mixin with no
        SQLAlchemy base at all - event registration in __init_subclass__
        must swallow the resulting InvalidRequestError gracefully instead of
        blowing up class definition for this fully legitimate, DB-free use
        case (decoupled from fastkit-core: no database required just to get
        locale-aware fields).
        """
        class PlainNote(TranslatableMixin):
            __translatable__ = ['title']

        note = PlainNote()
        note.set_locale('en')
        note.title = "Hello"
        note.set_locale('es')
        note.title = "Hola"

        note.set_locale('en')
        assert note.title == "Hello"
        assert note.get_translations('title') == {'en': 'Hello', 'es': 'Hola'}

    def test_get_translation_invalid_field_raises(self, session):
        """get_translation() (not just get_translations()/set_translation()) should validate the field."""
        article = Article(author="John")

        with pytest.raises(ValueError, match="not translatable"):
            article.get_translation('author')

    def test_load_event_with_unset_field(self, session):
        """Reloading a row where a translatable field was never set should yield an empty dict, not an error."""
        article = Article(author="John")
        set_locale('en')
        article.title = "Hello"
        # content is intentionally never set

        session.add(article)
        session.commit()

        session.expire_all()
        loaded = session.query(Article).first()

        assert loaded.get_translations('content') == {}

    def test_deserialize_translations_with_legacy_json_string(self):
        """
        deserialize_translations() should parse a raw JSON *string* value
        into the internal translations dict.

        This is exercised as a direct unit call rather than through a real
        DB round-trip: with a properly declared SQLAlchemy `JSON` column
        (as documented/required), the dialect's own JSON type decodes the
        column value *before* the ORM 'load' event ever sees it, so
        deserialize_translations() only ever receives an already-parsed
        dict in real usage - it can't naturally receive a raw string via
        that path. This branch exists to tolerate a value coming from
        elsewhere (a differently-configured column, a direct dict
        assignment bypassing the JSON layer, etc.), so it's tested directly.
        """
        from fastkit_i18n.database.translatable import deserialize_translations
        import json as json_module

        article = Article(author="John")
        object.__setattr__(article, 'title', json_module.dumps({"en": "Legacy Title"}))

        deserialize_translations(article, context=None)

        assert article.get_translations('title') == {"en": "Legacy Title"}

    def test_deserialize_translations_with_non_json_legacy_string(self):
        """
        deserialize_translations() should treat a raw non-JSON string as a
        single translation in the fallback locale rather than raising.
        See the note above about why this is a direct unit call.
        """
        from fastkit_i18n.database.translatable import deserialize_translations

        article = Article(author="John")
        object.__setattr__(article, 'title', "Just A Plain String")

        deserialize_translations(article, context=None)

        set_locale('en')
        assert article.title == "Just A Plain String"

    def test_standalone_mixin_swallows_invalidrequesterror_in_cold_process(self):
        """
        Confirms the try/except around event.listen() in __init_subclass__
        actually swallows InvalidRequestError for a plain, non-ORM class -
        not just that such a class works (test_works_standalone_without_any_orm_base
        above), but specifically that the exception path is taken.

        Must run in a subprocess: once *any* SQLAlchemy declarative base has
        been mapped earlier in the process (true for the rest of this test
        session, since Article/Product are defined at module import time),
        SQLAlchemy accepts event.listen() on any plain class without
        complaint, and the except branch is never actually reached.
        """
        import subprocess
        import sys
        import textwrap

        script = textwrap.dedent("""
            from fastkit_i18n import TranslatableMixin

            class PlainNote(TranslatableMixin):
                __translatable__ = ["title"]

            note = PlainNote()
            note.set_locale("en")
            note.title = "Hello"
            assert note.title == "Hello"
            print("OK")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout

    def test_set_locale_from_request_helper(self, session):
        """The FastAPI-docstring helper should set the shared global/context locale."""
        from fastkit_i18n import set_locale_from_request

        set_locale_from_request('es')

        article = Article(author="John")
        assert article.get_locale() == 'es'
