from pydantic import SecretStr
from sqlalchemy.engine import make_url

from backend.app.config import Settings


def test_default_database_url_uses_postgresql_and_psycopg() -> None:
    settings = Settings()
    url = make_url(settings.database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "ai_quant"


def test_asharehub_api_key_is_masked_in_settings_repr() -> None:
    settings = Settings(asharehub_api_key=SecretStr("test-secret"))

    assert settings.asharehub_api_key is not None
    assert settings.asharehub_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)
