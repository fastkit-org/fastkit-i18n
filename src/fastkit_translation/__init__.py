from .locale import set_locale, set_default_locale, get_default_locale, get_locale
from .i18n.translation import (
    TranslationManager,
    get_translation_manager,
    set_translation_manager,
    _,
    gettext,
    get_manager_locale,
    set_manager_locale
)

from .middleware.middleware import LocaleMiddleware

__all__ = [
    'set_locale',
    'set_default_locale',
    'get_default_locale',
    'get_locale',
    'TranslationManager',
    'get_manager_locale',
    'get_translation_manager',
    'set_manager_locale',
    'set_translation_manager',
    '_',
    'gettext',
    'LocaleMiddleware'
]
# NOTE: 'TranslatableMixin' and 'set_locale_from_request' are intentionally
# NOT in __all__. They're still importable explicitly - that's unaffected
# by __all__ - but `from fastkit_translation import *` walks every name in
# __all__ and calls getattr() on it, which would eagerly trigger the
# SQLAlchemy import below for anyone doing a wildcard import, even if they
# never touch TranslatableMixin. Keeping them out of __all__ preserves the
# zero-dependency guarantee for `import *` users too.

# TranslatableMixin / set_locale_from_request need SQLAlchemy. Import them
# lazily (PEP 562) so `import fastkit_translation` - and everything above -
# keeps working with zero dependencies when the database mixin isn't used.
# `from fastkit_translation import TranslatableMixin` still works as normal;
# the SQLAlchemy import (and its friendly error if missing) only happens the
# first time it's actually accessed.
def __getattr__(name):
    if name in ('TranslatableMixin', 'set_locale_from_request'):
        from .database.translatable import TranslatableMixin, set_locale_from_request
        globals()['TranslatableMixin'] = TranslatableMixin
        globals()['set_locale_from_request'] = set_locale_from_request
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")