from sqlalchemy.engine import make_url

from backend.app.config import Settings


def test_default_database_url_uses_postgresql_and_psycopg() -> None:
    settings = Settings()
    url = make_url(settings.database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "ai_quant"
