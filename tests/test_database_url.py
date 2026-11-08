from backend.app.db import _sqlalchemy_database_url


def test_fly_managed_postgres_url_uses_psycopg3():
    url = "postgresql://fly-user:secret@pg.example/fly-db"
    assert _sqlalchemy_database_url(url) == (
        "postgresql+psycopg://fly-user:secret@pg.example/fly-db"
    )


def test_legacy_postgres_url_uses_psycopg3():
    url = "postgres://fly-user:secret@pg.example/fly-db"
    assert _sqlalchemy_database_url(url) == (
        "postgresql+psycopg://fly-user:secret@pg.example/fly-db"
    )


def test_explicit_psycopg_url_is_unchanged():
    url = "postgresql+psycopg://user:secret@db.example/app"
    assert _sqlalchemy_database_url(url) == url


def test_sqlite_url_is_unchanged():
    url = "sqlite:///./app.db"
    assert _sqlalchemy_database_url(url) == url
