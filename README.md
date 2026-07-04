<div align="center">
  <h1>FastKit i18n</h1>

Laravel-style i18n for FastAPI. JSON translation files, automatic locale detection, and translatable SQLAlchemy/SQLModel models — without touching a framework. Pairs with [`fastkit-core`](https://fastkit.org/docs/fastkit-core) for translated Pydantic validation errors.

[![PyPI version](https://img.shields.io/pypi/v/fastkit-i18n.svg)](https://pypi.org/project/fastkit-i18n)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Part of FastKit](https://img.shields.io/badge/part%20of-FastKit-6c47ff)](https://fastkit.org)

  [![FastAPI](https://img.shields.io/badge/topic-fastapi-009688?style=flat-square)](https://github.com/topics/fastapi)
  [![i18n](https://img.shields.io/badge/topic-i18n-orange?style=flat-square)](https://github.com/topics/i18n)
  [![Localization](https://img.shields.io/badge/topic-localization-blue?style=flat-square)](https://github.com/topics/localization)
</div>

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

`fastkit-i18n` solves all three problems with one install.

---

## Installation

```bash
pip install fastkit-i18n
```

**Requirements:** Python 3.10+, no mandatory dependencies beyond the standard library. The `TranslatableMixin` needs SQLAlchemy — install it with `pip install fastkit-i18n[sqlalchemy]` when you need it. `_()` and `LocaleMiddleware` need nothing extra.

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
from fastkit_i18n import TranslationManager, set_translation_manager
from fastkit_i18n.middleware import LocaleMiddleware

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
from fastkit_i18n import _

_("messages.welcome", name="Maria")            # → "Welcome, Maria!"
_("messages.welcome", name="Maria", locale="de")  # → "Willkommen, Maria!"
```

The locale set by `LocaleMiddleware` per request is picked up automatically — no need to pass it explicitly in route handlers.

---

## Features

### `_()` — translation helper

Laravel-style dot notation with named interpolation:

```python
from fastkit_i18n import _

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
from fastkit_i18n import TranslatableMixin

class Article(TranslatableMixin, Base):
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

#### Works with SQLModel too

`SQLModel` is built directly on top of SQLAlchemy's ORM (a `SQLModel(table=True)` class *is* a real SQLAlchemy mapped class), so `TranslatableMixin` works with it the same way — no separate integration needed:

```python
from sqlmodel import SQLModel, Field, Column, JSON
from fastkit_i18n import TranslatableMixin

class Article(TranslatableMixin, SQLModel, table=True):
    __translatable__ = ["title", "content"]

    id: int | None = Field(default=None, primary_key=True)
    title: dict = Field(sa_column=Column(JSON))
    content: dict = Field(sa_column=Column(JSON))
```

**`TranslatableMixin` must come first in the base class list.** It overrides `__setattr__`/`__getattribute__` to make translatable fields look like plain strings, and it doesn't cooperate with `super()` there — if `SQLModel` (or any other class that also overrides these) comes first, its version wins for writes while `TranslatableMixin`'s still wins for reads, so a field can silently look empty instead of raising an error. Get the order backwards and `fastkit-i18n` raises a `TypeError` immediately when the class is defined, telling you exactly what to fix — it doesn't fail silently at runtime.

**Known limitation:** because writes to translatable fields bypass Pydantic's own attribute bookkeeping, they don't show up in `model_fields_set`. If you rely on `article.model_dump(exclude_unset=True)`, translatable fields you've set will be excluded as if untouched. Use `get_translations()` / `has_translation()` instead of `model_dump()` when you need to know which translatable fields were actually set.

---

### Translated Pydantic validation errors

Formatting a Pydantic `ValidationError` into per-language messages isn't something `fastkit-i18n` does itself — mapping error types (`missing`, `string_too_short`, `value_error.email`, ...) to messages is validation-framework logic, not i18n logic, and keeping it out keeps this package dependency-free for that use case.

What `fastkit-i18n` provides is the primitive that logic is built on: `_()`, already resolving to the correct per-request locale via `LocaleMiddleware`. In the FastKit ecosystem this formatting lives in [`fastkit-core`](https://fastkit.org/docs/fastkit-core), which calls straight into `_()`:

```python
# Inside fastkit-core's error formatter (not part of this package)
from fastkit_i18n import _

_("validation.required", field="title")
# → "The title field is required." (or the current request's locale)
```

If you're not using `fastkit-core`, you can write the same kind of formatter yourself — walk `exc.errors()`, map each `error['type']` to a `validation.*` key (see the file format below for the suggested key names), and call `_()`.

---

## Using with FastKit Core

`fastkit-i18n` is the standalone extraction of the i18n module from [`fastkit-core`](https://fastkit.org/docs/fastkit-core). If you use `fastkit-core`, you already have these features — no separate install needed.

Install just translations:
```bash
pip install fastkit-i18n
```

Or install the full FastKit toolkit:
```bash
pip install fastkit-core  # includes fastkit-i18n
```

---

## Why not `babel` or `gettext`?

`babel` and `gettext` are excellent tools, but they require a compilation step (`.po` → `.mo`), binary files in your repo, and a non-trivial setup process. For most FastAPI applications, JSON files are simpler to manage, easy to version in Git, straightforward to edit by non-developers, and ready to sync with translation platforms like Crowdin or Weblate.

`fastkit-i18n` is intentionally focused on JSON-based translations. If you need `.po`/`.mo` support, `babel` is the right tool.

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

`fastkit-i18n` is part of [FastKit](https://fastkit.org) — a collection of production-tested building blocks for FastAPI that bring the developer experience of Laravel to the Python ecosystem.

| Package | Description |
|---|---|
| [`fastkit-core`](https://pypi.org/project/fastkit-core) | Full toolkit — repository pattern, service layer, caching, events, HTTP utilities |
| [`fastkit-i18n`](https://pypi.org/project/fastkit-i18n) | This package — i18n standalone |
| [`fastkit-cli`](https://pypi.org/project/fastkit-cli) | Code generation — scaffold modules, manage migrations and seeders |
| [`mailbridge`](https://pypi.org/project/mailbridge) | Multi-provider email for any Python project |

---

## Documentation

Full documentation at [fastkit.org/docs/fastkit-i18n](https://fastkit.org/docs/fastkit-i18n)

---

## License

MIT — see [LICENSE](LICENSE)