from pydantic import SecretStr
from sqlalchemy.engine import make_url

from backend.app.config import Settings


def test_default_database_url_uses_postgresql_and_psycopg() -> None:
    settings = Settings()
    url = make_url(settings.database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "ai_quant"


def test_default_cors_origin_is_local_frontend() -> None:
    settings = Settings()

    assert settings.cors_origins == ["http://localhost:5173"]


def test_asharehub_api_key_is_masked_in_settings_repr() -> None:
    settings = Settings(asharehub_api_key=SecretStr("test-secret"))

    assert settings.asharehub_api_key is not None
    assert settings.asharehub_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)


def test_asharehub_sync_defaults_are_bounded() -> None:
    settings = Settings()

    assert settings.asharehub_timeout_seconds == 20
    assert settings.asharehub_sync_max_requests == 20
    assert settings.market_data_provider == "auto"


def test_ai_provider_is_disabled_without_explicit_configuration() -> None:
    settings = Settings()

    assert settings.ai_provider == "disabled"
    assert settings.ai_api_key is None
    assert settings.ai_model is None


def test_rag_defaults_to_local_fixed_dimension_embeddings() -> None:
    settings = Settings()

    assert settings.rag_embedding_provider == "local_hash"
    assert settings.rag_embedding_model == "local-hash-v1"
    assert settings.rag_embedding_dimensions == 256
