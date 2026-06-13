from backend.app.database.session import SessionLocal, engine


def test_session_factory_uses_postgresql_engine_without_connecting() -> None:
    assert engine.dialect.name == "postgresql"
    assert engine.url.drivername == "postgresql+psycopg"

    with SessionLocal() as session:
        assert session.bind is engine
