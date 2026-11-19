from sqlalchemy import make_url

from app.config import LocalSettings


def test_database_connection_uses_postgres_environment(monkeypatch):
    password = "local:p@ss/word#example"
    monkeypatch.setenv("POSTGRES_USER", "local_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    monkeypatch.setenv("POSTGRES_DB", "local_db")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.2")
    monkeypatch.setenv("POSTGRES_PORT", "15432")

    url = LocalSettings(_env_file=None).database_url

    assert make_url(url.render_as_string(hide_password=False)) == url
    assert url.username == "local_user"
    assert url.password == password
    assert url.database == "local_db"
    assert url.host == "127.0.0.2"
    assert url.port == 15432
