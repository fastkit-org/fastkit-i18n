"""
Tests for TranslationManager (fastkit_translation.i18n.translation).

Adapted from the original fastkit-core test suite for the standalone
fastkit-translation package:
- No more fastkit_core.config.ConfigManager - TranslationManager takes
  translations_dir/default_locale/fallback_locale directly, or falls back
  to the app-wide default set via fastkit_translation.locale.set_default_locale()
- manager.set_locale()/get_locale() renamed to set_manager_locale()/
  get_manager_locale() to avoid colliding with the context-level
  fastkit_translation.locale.set_locale()/get_locale() (which LocaleMiddleware
  uses per-request)
"""

import pytest
import json

from fastkit_translation import (
    TranslationManager,
    get_translation_manager,
    set_translation_manager,
    _,
    gettext,
    set_manager_locale,
    get_manager_locale,
    set_locale,
    get_locale,
)
from fastkit_translation.locale import _current_locale, set_default_locale


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def translations_dir(tmp_path):
    """Create temporary translations directory with test files."""
    trans_dir = tmp_path / "translations"
    trans_dir.mkdir()

    # English translations
    en_content = {
        "messages": {
            "welcome": "Welcome!",
            "hello": "Hello, {name}!",
            "goodbye": "Goodbye, {name}!",
            "items": "{count} item|{count} items"
        },
        "errors": {
            "not_found": "Not found",
            "server_error": "Server error"
        },
        "validation": {
            "required": "The {field} field is required",
            "email": "The {field} must be a valid email"
        },
        "nested": {
            "level1": {
                "level2": {
                    "deep": "Deep value"
                }
            }
        }
    }

    with open(trans_dir / "en.json", "w", encoding="utf-8") as f:
        json.dump(en_content, f, ensure_ascii=False, indent=2)

    # Spanish translations
    es_content = {
        "messages": {
            "welcome": "¡Bienvenido!",
            "hello": "¡Hola, {name}!",
            "goodbye": "¡Adiós, {name}!",
            "items": "{count} artículo|{count} artículos"
        },
        "errors": {
            "not_found": "No encontrado",
            "server_error": "Error del servidor"
        },
        "validation": {
            "required": "El campo {field} es obligatorio",
            "email": "El campo {field} debe ser un correo válido"
        }
    }

    with open(trans_dir / "es.json", "w", encoding="utf-8") as f:
        json.dump(es_content, f, ensure_ascii=False, indent=2)

    # French translations (partial - for fallback testing)
    fr_content = {
        "messages": {
            "welcome": "Bienvenue!",
            "hello": "Bonjour, {name}!"
        }
    }

    with open(trans_dir / "fr.json", "w", encoding="utf-8") as f:
        json.dump(fr_content, f, ensure_ascii=False, indent=2)

    return trans_dir


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global translation manager, context locale and app default before each test."""
    import fastkit_translation.i18n.translation as translation_module
    translation_module._translation_manager = None
    _current_locale.set(None)
    set_default_locale('en')

    yield

    translation_module._translation_manager = None
    _current_locale.set(None)
    set_default_locale('en')


@pytest.fixture
def manager(translations_dir):
    """Create TranslationManager instance pointed at the temp translations dir."""
    return TranslationManager(translations_dir=translations_dir, default_locale='en', fallback_locale='en')


# ============================================================================
# Test TranslationManager Initialization
# ============================================================================

class TestTranslationManagerInit:
    """Test TranslationManager initialization."""

    def test_init_with_explicit_path(self, translations_dir):
        """Should initialize with explicit translations directory."""
        manager = TranslationManager(translations_dir=translations_dir)

        assert manager.translations_dir == translations_dir
        assert len(manager._translations) > 0

    def test_init_uses_app_default_locale(self, translations_dir):
        """Should fall back to the app-wide default locale when not given explicitly."""
        set_default_locale('de')

        manager = TranslationManager(translations_dir=translations_dir)

        assert manager.default_locale == 'de'
        # fallback_locale defaults to default_locale when not specified
        assert manager.fallback_locale == 'de'

    def test_init_explicit_locale_overrides_app_default(self, translations_dir):
        """Explicit default_locale/fallback_locale should win over the app-wide default."""
        set_default_locale('de')

        manager = TranslationManager(
            translations_dir=translations_dir,
            default_locale='en',
            fallback_locale='fr',
        )

        assert manager.default_locale == 'en'
        assert manager.fallback_locale == 'fr'

    def test_init_nonexistent_directory(self, tmp_path):
        """Should handle nonexistent translations directory."""
        nonexistent = tmp_path / "nonexistent"
        manager = TranslationManager(translations_dir=nonexistent)

        assert manager._translations == {}

    def test_load_multiple_locales(self, manager):
        """Should load all locale files."""
        assert 'en' in manager._translations
        assert 'es' in manager._translations
        assert 'fr' in manager._translations


# ============================================================================
# Test Translation File Loading
# ============================================================================

class TestTranslationLoading:
    """Test translation file loading."""

    def test_load_valid_json(self, manager):
        """Should load valid JSON files."""
        assert 'messages' in manager._translations['en']
        assert 'errors' in manager._translations['en']

    def test_load_utf8_content(self, manager):
        """Should handle UTF-8 content correctly."""
        welcome_es = manager._translations['es']['messages']['welcome']
        assert '¡' in welcome_es
        assert 'Bienvenido' in welcome_es

    def test_load_nested_structure(self, manager):
        """Should load nested JSON structure."""
        nested = manager._translations['en']['nested']
        assert 'level1' in nested
        assert 'level2' in nested['level1']
        assert 'deep' in nested['level1']['level2']

    def test_load_invalid_json(self, tmp_path):
        """Should handle invalid JSON gracefully."""
        trans_dir = tmp_path / "bad_translations"
        trans_dir.mkdir()

        # Create invalid JSON file
        bad_file = trans_dir / "bad.json"
        bad_file.write_text("{invalid json content!!!")

        manager = TranslationManager(translations_dir=trans_dir)

        # Should not have loaded bad file
        assert 'bad' not in manager._translations

    def test_load_empty_json_file(self, tmp_path):
        """Should handle empty JSON file."""
        trans_dir = tmp_path / "empty_translations"
        trans_dir.mkdir()

        empty_file = trans_dir / "empty.json"
        empty_file.write_text("{}")

        manager = TranslationManager(translations_dir=trans_dir)

        assert 'empty' in manager._translations
        assert manager._translations['empty'] == {}

    def test_ignore_non_json_files(self, tmp_path):
        """Should ignore non-JSON files."""
        trans_dir = tmp_path / "mixed_translations"
        trans_dir.mkdir()

        # Create JSON file
        (trans_dir / "en.json").write_text('{"test": "value"}')

        # Create non-JSON files
        (trans_dir / "readme.txt").write_text("readme")
        (trans_dir / "config.yaml").write_text("test: value")

        manager = TranslationManager(translations_dir=trans_dir)

        assert 'en' in manager._translations
        assert 'readme' not in manager._translations
        assert 'config' not in manager._translations


# ============================================================================
# Test Translation Retrieval (get)
# ============================================================================

class TestTranslationGet:
    """Test translation retrieval."""

    def test_get_simple_key(self, manager):
        """Should get simple translation."""
        result = manager.get('messages.welcome', locale='en')
        assert result == "Welcome!"

    def test_get_with_dot_notation(self, manager):
        """Should access nested keys with dot notation."""
        result = manager.get('errors.not_found', locale='en')
        assert result == "Not found"

    def test_get_deeply_nested(self, manager):
        """Should access deeply nested keys."""
        result = manager.get('nested.level1.level2.deep', locale='en')
        assert result == "Deep value"

    def test_get_nonexistent_key(self, manager):
        """Should return key if translation not found."""
        result = manager.get('nonexistent.key', locale='en')
        assert result == 'nonexistent.key'

    def test_get_with_variable_replacement(self, manager):
        """Should replace variables in translation."""
        result = manager.get('messages.hello', locale='en', name='John')
        assert result == "Hello, John!"

    def test_get_with_multiple_variables(self, manager):
        """Should replace multiple variables."""
        # Add translation with multiple variables
        manager._translations['en']['test'] = {'multi': '{first} and {second}'}

        result = manager.get('test.multi', locale='en', first='A', second='B')
        assert result == "A and B"

    def test_get_with_missing_variable(self, manager):
        """Should handle missing variable gracefully."""
        result = manager.get('messages.hello', locale='en')
        # Should still return string with placeholder
        assert '{name}' in result

    def test_get_different_locales(self, manager):
        """Should get translations for different locales."""
        en_result = manager.get('messages.welcome', locale='en')
        es_result = manager.get('messages.welcome', locale='es')

        assert en_result == "Welcome!"
        assert es_result == "¡Bienvenido!"

    def test_get_uses_current_locale(self, manager):
        """Should use current context locale if not specified."""
        manager.set_manager_locale('es')
        result = manager.get('messages.welcome')
        assert result == "¡Bienvenido!"

    def test_get_uses_default_locale(self, manager):
        """Should use default locale if no context locale set."""
        result = manager.get('messages.welcome')
        assert result == "Welcome!"


# ============================================================================
# Test Fallback Behavior
# ============================================================================

class TestFallbackBehavior:
    """Test locale fallback behavior."""

    def test_fallback_to_default_locale(self, manager):
        """Should fallback to default locale for missing key."""
        # French has 'welcome' but not 'goodbye'
        result = manager.get('messages.goodbye', locale='fr', name='John')

        # Should fallback to English
        assert result == "Goodbye, John!"

    def test_fallback_for_missing_locale(self, manager):
        """Should fallback to default for nonexistent locale."""
        result = manager.get('messages.welcome', locale='de')

        # Should fallback to English
        assert result == "Welcome!"

    def test_no_fallback_when_disabled(self, manager):
        """Should not fallback when disabled."""
        result = manager.get('messages.goodbye', locale='fr', fallback=False)

        # Should return key, not fallback
        assert result == 'messages.goodbye'

    def test_fallback_with_variables(self, manager):
        """Should apply variables after fallback."""
        # French missing 'goodbye', fallback to English
        result = manager.get('messages.goodbye', locale='fr', name='Marie')

        assert result == "Goodbye, Marie!"

    def test_no_fallback_loop(self, manager):
        """Should not fallback if locale is same as fallback."""
        manager.fallback_locale = 'en'

        # Key doesn't exist in English
        result = manager.get('nonexistent.key', locale='en')

        # Should return key, not loop
        assert result == 'nonexistent.key'


# ============================================================================
# Test Locale Management
# ============================================================================

class TestLocaleManagement:
    """Test locale setting and getting."""

    def test_set_locale(self, manager):
        """Should set current locale."""
        manager.set_manager_locale('es')
        assert manager.get_manager_locale() == 'es'

    def test_get_locale_default(self, manager):
        """Should return default locale if not set."""
        locale = manager.get_manager_locale()
        assert locale == 'en'

    def test_locale_context_shared(self, manager):
        """Should share locale context with TranslatableMixin."""
        manager.set_manager_locale('es')

        # Context should be set
        assert _current_locale.get() == 'es'

    def test_set_locale_affects_get(self, manager):
        """Should affect subsequent get() calls."""
        manager.set_manager_locale('es')
        result = manager.get('messages.welcome')
        assert result == "¡Bienvenido!"

        manager.set_manager_locale('fr')
        result = manager.get('messages.welcome')
        assert result == "Bienvenue!"

    def test_get_with_explicit_locale_overrides_context(self, manager):
        """Should override context locale when explicit."""
        manager.set_manager_locale('es')

        # Explicit locale should override context
        result = manager.get('messages.welcome', locale='en')
        assert result == "Welcome!"


# ============================================================================
# Test Helper Methods
# ============================================================================

class TestHelperMethods:
    """Test utility helper methods."""

    def test_has_existing_key(self, manager):
        """Should return True for existing key."""
        assert manager.has('messages.welcome', locale='en') is True

    def test_has_nonexistent_key(self, manager):
        """Should return False for nonexistent key."""
        assert manager.has('nonexistent.key', locale='en') is False

    def test_has_with_current_locale(self, manager):
        """Should use current locale if not specified."""
        manager.set_manager_locale('es')
        assert manager.has('messages.welcome') is True

    def test_has_nonexistent_locale(self, manager):
        """Should return False for nonexistent locale."""
        assert manager.has('messages.welcome', locale='de') is False

    def test_get_all_for_locale(self, manager):
        """Should get all translations for locale."""
        all_trans = manager.get_all('en')

        assert 'messages' in all_trans
        assert 'errors' in all_trans
        assert all_trans['messages']['welcome'] == "Welcome!"

    def test_get_all_current_locale(self, manager):
        """Should use current locale if not specified."""
        manager.set_manager_locale('es')
        all_trans = manager.get_all()

        assert all_trans['messages']['welcome'] == "¡Bienvenido!"

    def test_get_available_locales(self, manager):
        """Should return list of available locales."""
        locales = manager.get_available_locales()

        assert 'en' in locales
        assert 'es' in locales
        assert 'fr' in locales
        assert len(locales) == 3

    def test_reload_translations(self, manager, translations_dir):
        """Should reload translation files."""
        # Modify translation
        manager._translations['en']['messages']['welcome'] = 'Changed'

        # Reload
        manager.reload()

        # Should be back to original
        assert manager.get('messages.welcome', locale='en') == "Welcome!"

    def test_reload_picks_up_new_files(self, manager, translations_dir):
        """Should pick up new translation files on reload."""
        # Add new locale file
        de_content = {"messages": {"welcome": "Willkommen!"}}
        with open(translations_dir / "de.json", "w") as f:
            json.dump(de_content, f)

        # Reload
        manager.reload()

        # Should have new locale
        assert 'de' in manager._translations
        assert manager.get('messages.welcome', locale='de') == "Willkommen!"


# ============================================================================
# Test Global Functions
# ============================================================================

class TestGlobalFunctions:
    """Test global helper functions."""

    def test_get_translation_manager(self):
        """Should get global translation manager."""
        manager = get_translation_manager()

        assert manager is not None
        assert isinstance(manager, TranslationManager)

    def test_get_translation_manager_singleton(self):
        """Should return same instance."""
        manager1 = get_translation_manager()
        manager2 = get_translation_manager()

        assert manager1 is manager2

    def test_set_translation_manager(self, translations_dir):
        """Should set custom global manager."""
        custom_manager = TranslationManager(translations_dir=translations_dir)
        set_translation_manager(custom_manager)

        assert get_translation_manager() is custom_manager

    def test_underscore_helper(self, translations_dir):
        """Should translate using _ helper."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        result = _('messages.welcome', locale='en')
        assert result == "Welcome!"

    def test_underscore_with_variables(self, translations_dir):
        """Should handle variables with _ helper."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        result = _('messages.hello', locale='en', name='John')
        assert result == "Hello, John!"

    def test_underscore_uses_context_locale(self, translations_dir):
        """Should use context locale with _ helper."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        set_locale('es')
        result = _('messages.welcome')
        assert result == "¡Bienvenido!"

    def test_gettext_alias(self, translations_dir):
        """Should work as alias for _."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        result = gettext('messages.welcome', locale='en')
        assert result == "Welcome!"

    def test_set_locale_function(self):
        """Should set locale via the shared context-level function."""
        set_locale('es')
        assert get_locale() == 'es'

    def test_get_locale_function(self):
        """Should get locale via the shared context-level function."""
        locale = get_locale()
        assert locale == 'en'  # Default


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_key(self, manager):
        """Should handle empty key."""
        result = manager.get('', locale='en')
        assert result == ''

    def test_key_with_only_dots(self, manager):
        """Should handle key with only dots."""
        result = manager.get('...', locale='en')
        assert result == '...'

    def test_very_long_key(self, manager):
        """Should handle very long key."""
        long_key = '.'.join(['level'] * 100)
        result = manager.get(long_key, locale='en')
        assert result == long_key

    def test_special_characters_in_values(self, manager):
        """Should handle special characters."""
        manager._translations['en']['test'] = {
            'special': '!@#$%^&*(){}[]|\\<>?,./"\':;'
        }

        result = manager.get('test.special', locale='en')
        assert result == '!@#$%^&*(){}[]|\\<>?,./"\':;'

    def test_unicode_in_keys_and_values(self, manager):
        """Should handle Unicode."""
        manager._translations['en']['test'] = {
            'unicode': '你好世界 🌍 Привет مرحبا'
        }

        result = manager.get('test.unicode', locale='en')
        assert '你好世界' in result
        assert '🌍' in result

    def test_none_as_translation_value(self, manager):
        """Should handle None values."""
        manager._translations['en']['test'] = {'null': None}

        result = manager.get('test.null', locale='en')
        # Should return key if value is not string
        assert result == 'test.null'

    def test_number_as_translation_value(self, manager):
        """Should handle number values."""
        manager._translations['en']['test'] = {'number': 42}

        result = manager.get('test.number', locale='en')
        # Should return key if value is not string
        assert result == 'test.number'

    def test_list_as_translation_value(self, manager):
        """Should handle list values."""
        manager._translations['en']['test'] = {'list': ['a', 'b', 'c']}

        result = manager.get('test.list', locale='en')
        # Should return key if value is not string
        assert result == 'test.list'

    def test_empty_string_translation(self, manager):
        """Should handle empty string translations."""
        manager._translations['en']['test'] = {'empty': ''}

        result = manager.get('test.empty', locale='en')
        assert result == ''

    def test_whitespace_only_translation(self, manager):
        """Should handle whitespace-only translations."""
        manager._translations['en']['test'] = {'spaces': '   '}

        result = manager.get('test.spaces', locale='en')
        assert result == '   '

    def test_variable_replacement_with_empty_value(self, manager):
        """Should handle empty variable values."""
        result = manager.get('messages.hello', locale='en', name='')
        assert result == "Hello, !"

    def test_variable_replacement_with_special_chars(self, manager):
        """Should handle special chars in variable values."""
        result = manager.get('messages.hello', locale='en', name='<script>')
        assert result == "Hello, <script>!"


# ============================================================================
# Test Integration Scenarios
# ============================================================================

class TestIntegration:
    """Test real-world integration scenarios."""

    def test_typical_web_app_usage(self, translations_dir):
        """Should work in typical web app scenario."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        # Set user's locale (e.g., from request header, via LocaleMiddleware)
        set_locale('es')

        # Use in code
        welcome = _('messages.welcome')
        greeting = _('messages.hello', name='María')
        error = _('errors.not_found')

        assert welcome == "¡Bienvenido!"
        assert greeting == "¡Hola, María!"
        assert error == "No encontrado"

    def test_validation_error_messages(self, translations_dir):
        """Should work for validation error messages."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        set_locale('en')

        # Simulate validation errors
        email_error = _('validation.email', field='email')
        required_error = _('validation.required', field='username')

        assert email_error == "The email must be a valid email"
        assert required_error == "The username field is required"

    def test_multi_user_concurrent_locales(self, translations_dir):
        """Should handle different locales in concurrent requests."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        # User 1: English
        set_locale('en')
        result_en = _('messages.welcome')

        # User 2: Spanish
        set_locale('es')
        result_es = _('messages.welcome')

        # User 3: French
        set_locale('fr')
        result_fr = _('messages.welcome')

        # Each should get their locale
        # (Note: in real concurrent scenarios, use async context / per-request tokens)
        assert result_en == "Welcome!"
        assert result_es == "¡Bienvenido!"
        assert result_fr == "Bienvenue!"

    def test_missing_translation_graceful_degradation(self, translations_dir):
        """Should degrade gracefully for missing translations."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        set_locale('fr')

        # French has 'welcome' but not 'goodbye'
        # Should fallback to English
        welcome = _('messages.welcome')
        goodbye = _('messages.goodbye', name='User')

        assert welcome == "Bienvenue!"  # French
        assert goodbye == "Goodbye, User!"  # English fallback

    def test_dynamic_locale_switching(self, translations_dir):
        """Should handle dynamic locale switching."""
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        # Start with English
        set_locale('en')
        result1 = _('messages.welcome')
        assert result1 == "Welcome!"

        # Switch to Spanish
        set_locale('es')
        result2 = _('messages.welcome')
        assert result2 == "¡Bienvenido!"

        # Switch to French
        set_locale('fr')
        result3 = _('messages.welcome')
        assert result3 == "Bienvenue!"


# ============================================================================
# Test Coverage Gaps
#
# Added after reviewing `pytest --cov` output: each of these exercises a
# branch that was otherwise never hit by the tests above.
# ============================================================================

class TestCoverageGaps:
    """Targeted tests for branches missed by the rest of the suite."""

    def test_get_with_unknown_locale_and_fallback_disabled_returns_key(self, manager):
        """
        Should return the raw key when the requested locale doesn't exist
        at all AND fallback is disabled - distinct from the case where the
        locale exists but the key is missing (covered elsewhere).
        """
        result = manager.get('messages.welcome', locale='xx', fallback=False)
        assert result == 'messages.welcome'

    def test_replace_variables_missing_placeholder_value(self, manager):
        """
        Should leave the string as-is (with the unresolved placeholder) when
        replacements are provided but don't cover every {placeholder} in the
        template, instead of raising.
        """
        manager._translations['en']['test'] = {'multi': '{first} and {second}'}

        # Only 'first' provided - template also needs 'second'
        result = manager.get('test.multi', locale='en', first='A')

        assert result == '{first} and {second}'

    def test_module_level_set_and_get_manager_locale(self, translations_dir):
        """
        The free functions set_manager_locale()/get_manager_locale() (thin
        wrappers around the global manager) should work, not just the
        TranslationManager instance methods.
        """
        set_translation_manager(TranslationManager(translations_dir=translations_dir))

        set_manager_locale('es')
        assert get_manager_locale() == 'es'

        result = _('messages.welcome')
        assert result == "¡Bienvenido!"
