"""
Regression tests for TranslatableMixin + SQLModel compatibility.

SQLModel is built directly on SQLAlchemy's ORM, so TranslatableMixin works
with it the same way it works with plain SQLAlchemy declarative models - but
two real bugs were found and fixed while building this out, and both are
easy to reintroduce by accident, so they're pinned down here:

1. MRO order: TranslatableMixin overrides __setattr__/__getattribute__ and
   does not cooperate with super() there. If another base class (like
   SQLModel/pydantic's BaseModel) also overrides these and comes first in
   the MRO, writes and reads silently split across two different
   implementations - a field can end up looking empty with no error at all.
   __init_subclass__ must catch this at class-definition time.

2. Import order: registering the (de)serialization events at module level
   on the bare TranslatableMixin class (`event.listens_for(TranslatableMixin,
   'load', propagate=True)`) only works if some SQLAlchemy declarative base
   has already been mapped earlier in the process - otherwise SQLAlchemy
   raises InvalidRequestError. Events must be registered per-concrete-class
   instead, so behavior doesn't depend on unrelated import order elsewhere
   in the app.
"""

import subprocess
import sys
import textwrap

import pytest
from sqlmodel import SQLModel, Field, Column, JSON, create_engine, Session

from fastkit_translation import TranslatableMixin
from fastkit_translation.locale import set_locale


@pytest.fixture(autouse=True)
def reset_locale():
    set_locale('en')
    yield
    set_locale('en')


def test_translatable_mixin_first_works_end_to_end():
    """TranslatableMixin first in the base list should work fully, including DB round-trips."""

    class Article(TranslatableMixin, SQLModel, table=True):
        __tablename__ = 'sqlmodel_articles'
        __translatable__ = ['title']
        __fallback_locale__ = 'en'

        id: int | None = Field(default=None, primary_key=True)
        title: dict = Field(default=None, sa_column=Column(JSON))

        model_config = {'arbitrary_types_allowed': True}

    article = Article()
    article.set_locale('en')
    article.title = "Hello World"
    article.set_locale('es')
    article.title = "Hola Mundo"

    article.set_locale('en')
    assert article.title == "Hello World"
    assert article.get_translations('title') == {'en': 'Hello World', 'es': 'Hola Mundo'}

    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(article)
        session.commit()
        session.refresh(article)
        article_id = article.id

    with Session(engine) as session:
        loaded = session.get(Article, article_id)
        loaded.set_locale('es')
        assert loaded.title == "Hola Mundo"
        loaded.set_locale('en')
        assert loaded.title == "Hello World"


def test_sqlmodel_first_raises_typeerror_at_class_definition():
    """Wrong MRO order must fail loudly at class definition, not silently at runtime."""

    with pytest.raises(TypeError, match="TranslatableMixin FIRST"):
        class Article(SQLModel, TranslatableMixin, table=True):
            __tablename__ = 'sqlmodel_articles_wrong_order'
            __translatable__ = ['title']

            id: int | None = Field(default=None, primary_key=True)
            title: dict = Field(default=None, sa_column=Column(JSON))

            model_config = {'arbitrary_types_allowed': True}


def test_translatable_mixin_is_first_sqlalchemy_import_in_process():
    """
    Importing fastkit_translation.database.translatable before touching any
    other SQLAlchemy declarative base must not raise.

    This has to run in a subprocess: once any other test in this session
    imports DeclarativeBase/SQLModel, the process-wide SQLAlchemy state is
    already warmed up and would mask a regression of the per-class event
    registration fix.
    """
    script = textwrap.dedent("""
        from fastkit_translation.database.translatable import TranslatableMixin
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
        from sqlalchemy import JSON

        class Base(DeclarativeBase):
            pass

        class Article(TranslatableMixin, Base):
            __tablename__ = "articles"
            __translatable__ = ["title"]
            id: Mapped[int] = mapped_column(primary_key=True)
            title: Mapped[dict] = mapped_column(JSON)

        a = Article()
        a.set_locale("en")
        a.title = "Hello"
        assert a.title == "Hello"
        print("OK")
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
