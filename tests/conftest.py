import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app, seed_tariffs


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_tariffs(db)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory, monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)

    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_payment(client, headers=None, **overrides):
    body = {"tariff_id": "standard", "email": "student@example.com", "method": "card"}
    body.update(overrides)
    return client.post("/payments", json=body, headers=headers or {})
