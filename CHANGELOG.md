# Changelog

All notable changes to `fastkit-translation` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-07-04

Initial stable release — standalone extraction of the i18n module from
`fastkit-core`, fully decoupled and independently installable.

### Added
- `_()` / `TranslationManager` — Laravel-style JSON translation files with
  dot-notation keys, `{variable}` interpolation, and locale fallback. Zero
  dependencies.
- `LocaleMiddleware` — pure ASGI middleware (no framework dependency) that
  detects locale from the `Accept-Language` header, `?lang=` query
  parameter, or `locale` cookie, in that priority order.
- `TranslatableMixin` — transparent multi-language fields for SQLAlchemy
  and SQLModel models. Works with plain SQLAlchemy declarative models,
  SQLModel table models, and even standalone (no ORM base at all).
- `fastkit_translation.locale` — shared app-wide default locale
  (`set_default_locale`/`get_default_locale`) and per-request context locale
  (`set_locale`/`get_locale`/`reset_locale`), used consistently by all three
  pieces above.
- `__init_subclass__` guard on `TranslatableMixin` that raises a clear
  `TypeError` at class-definition time if another base class (e.g. SQLModel)
  wins the MRO for `__setattr__`/`__getattribute__`, instead of silently
  losing translation data at runtime.
- `pip install fastkit-translation[sqlalchemy]` extra — the SQLAlchemy
  dependency is optional; `_()` and `LocaleMiddleware` need nothing beyond
  the standard library.
- `py.typed` marker — the package ships inline type annotations.

### Notes
- Requires Python 3.10+.
- No dependency on `fastkit-core`, Starlette, or Pydantic for the core
  translation/middleware features.
