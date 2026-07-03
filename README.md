# fastkit-translations

Laravel-style i18n for FastAPI. JSON translation files, automatic locale detection, translatable SQLAlchemy models, and translated Pydantic validation errors — without touching a framework.

[![PyPI version](https://img.shields.io/pypi/v/fastkit-translations.svg)](https://pypi.org/project/fastkit-translations)
[![Python](https://img.shields.io/pypi/pyversions/fastkit-translations.svg)](https://pypi.org/project/fastkit-translations)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Part of FastKit](https://img.shields.io/badge/part%20of-FastKit-6c47ff)](https://fastkit.org)

---

## The problem

FastAPI has no built-in answer for internationalization. Not in models, not in validation errors, not in responses. The typical approach looks like this:

```python
# Manual locale handling — repeated across every endpoint
article = session.get(Article, 1)
locale = request.headers.get("Accept-Language", "en")[:2]
title = article.title.get(locale) or article.title.get("en")  # manual fallback

# English-only Pydantic errors
# Inconsistent response shapes per endpoint
```

`fastkit-translations` solves all three problems with one install.

---

## Installation

```bash
pip install fastkit-translations
```

**Requirements:** Python 3.11+, no mandatory dependencies beyond the standard library. Optional integrations for SQLAlchemy and Pydantic are available.

---

## Quick start

### 1. Set up translation files

```
translations/
├── en.json
├── de.json
└── fr.json
```

```json
// translations/en.json
{
  "validation": {
    "required": "The {field} field is required.",
    "email": "The {field} field must be a valid email address."
  },
  "messages": {
    "welcome": "Welcome, {name}!",
    "created": "{resource} created successfully."
  }
}
```

### 2. Initialize at startup

```python
# main.py
from fastapi import FastAPI
from fastkit_translations import TranslationManager, set_translation_manager
from fastkit_translations.middleware import LocaleMiddleware

app = FastAPI()
app.add_middleware(LocaleMiddleware)

set_translation_manager(
    TranslationManager(
        translations_dir="translations/",
        default_locale="en",
        fallback_locale="en",
    )
)
```

### 3. Translate anywhere

```python
from fastkit_translations import _

_("messages.welcome", name="Maria")            # → "Welcome, Maria!"
_("messages.welcome", name="Maria", locale="de")  # → "Willkommen, Maria!"
```

The locale set by `LocaleMiddleware` per request is picked up automatically — no need to pass it explicitly in route handlers.

---

## Features

### `_()` — translation helper

Laravel-style dot notation with named interpolation:

```python
from fastkit_translations import _

# Simple key
_("validation.required")

# With interpolation
_("validation.string_too_short", field="name", min_length=3)

# Explicit locale — overrides request locale
_("messages.welcome", name="Ana", locale="fr")
```

---

### `LocaleMiddleware` — automatic locale detection

Register once. Every request sets the correct locale automatically.

```python
app.add_middleware(LocaleMiddleware)
```

Resolution order:

1. `Accept-Language` request header (e.g. `Accept-Language: de`)
2. `?lang=` query parameter (e.g. `/articles?lang=fr`)
3. `locale` cookie
4. Default locale from `TranslationManager`

---

### `TranslatableMixin` — i18n directly in SQLAlchemy models

Declare translatable fields once. Read and write them like normal strings — the mixin handles locale routing automatically.

```python
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column
from fastkit_translations.mixin import TranslatableMixin

class Article(Base, TranslatableMixin):
    __translatable__ = ["title", "content"]
    __fallback_locale__ = "en"

    title: Mapped[dict] = mapped_column(JSON)
    content: Mapped[dict] = mapped_column(JSON)
```

```python
article = Article()

# Write
article.set_locale("en")
article.title = "How to build scalable APIs"

article.set_locale("de")
article.title = "Wie man skalierbare APIs entwickelt"

# Read — always returns current locale with fallback
article.set_locale("fr")
print(article.title)  # "How to build scalable APIs" — English fallback

# All translations at once
article.get_translations("title")
# {"en": "How to build scalable APIs", "de": "Wie man skalierbare APIs entwickelt"}
```

With `LocaleMiddleware` registered, `article.title` reads the correct locale automatically per request — no `set_locale()` needed in route handlers.

---

### Translated Pydantic validation errors

`TranslatableMixin` works with any Pydantic `BaseModel` to format validation errors using your translation files:

```python
from pydantic import EmailStr, BaseModel
from fastkit_translations.validation import format_errors

class ArticleCreate(BaseModel):
    title: str
    email: EmailStr
```

```python
# Request with Accept-Language: de
try:
    ArticleCreate(title="", email="not-an-email")
except ValidationError as exc:
    errors = format_errors(exc)
    # {
    #   "title": ["Das Feld title ist erforderlich."],
    #   "email": ["Das Feld email muss eine gültige E-Mail-Adresse sein."]
    # }
```

---

## Using with FastKit Core

`fastkit-translations` is the standalone extraction of the i18n module from [`fastkit-core`](https://fastkit.org/docs/fastkit-core). If you use `fastkit-core`, you already have these features — no separate install needed.

Install just translations:
```bash
pip install fastkit-translations
```

Or install the full FastKit toolkit:
```bash
pip install fastkit-core  # includes fastkit-translations
```

---

## Why not `babel` or `gettext`?

`babel` and `gettext` are excellent tools, but they require a compilation step (`.po` → `.mo`), binary files in your repo, and a non-trivial setup process. For most FastAPI applications, JSON files are simpler to manage, easy to version in Git, straightforward to edit by non-developers, and ready to sync with translation platforms like Crowdin or Weblate.

`fastkit-translations` is intentionally focused on JSON-based translations. If you need `.po`/`.mo` support, `babel` is the right tool.

---

## Translation file format

Standard JSON with dot-notation keys and `{variable}` interpolation:

```json
{
  "validation": {
    "required": "The {field} field is required.",
    "string_too_short": "The {field} must be at least {min_length} characters.",
    "string_too_long": "The {field} must not exceed {max_length} characters.",
    "email": "The {field} must be a valid email address.",
    "unique": "The {field} has already been taken."
  },
  "auth": {
    "invalid_credentials": "Invalid email or password.",
    "unauthorized": "You are not authorized to perform this action."
  },
  "messages": {
    "welcome": "Welcome, {name}!",
    "created": "{resource} created successfully.",
    "updated": "{resource} updated successfully.",
    "deleted": "{resource} deleted successfully."
  }
}
```

---

## Part of the FastKit ecosystem

`fastkit-translations` is part of [FastKit](https://fastkit.org) — a collection of production-tested building blocks for FastAPI that bring the developer experience of Laravel to the Python ecosystem.

| Package | Description |
|---|---|
| [`fastkit-core`](https://pypi.org/project/fastkit-core) | Full toolkit — repository pattern, service layer, caching, events, HTTP utilities |
| [`fastkit-translations`](https://pypi.org/project/fastkit-translations) | This package — i18n standalone |
| [`fastkit-cli`](https://pypi.org/project/fastkit-cli) | Code generation — scaffold modules, manage migrations and seeders |
| [`mailbridge`](https://pypi.org/project/mailbridge) | Multi-provider email for any Python project |

---

## Documentation

Full documentation at [fastkit.org/docs/fastkit-translations](https://fastkit.org/docs/fastkit-translations)

---

## License

MIT — see [LICENSE](LICENSE)