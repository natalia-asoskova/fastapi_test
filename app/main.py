from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app import models
from app.db import Base, SessionLocal, engine
from app.routers import payments, tariffs, webhooks

SEED_TARIFFS = [
    ("basic", "Basic", 990_000),
    ("standard", "Standard", 1_990_000),
    ("premium", "Premium", 2_990_000),
]


def seed_tariffs(db: Session) -> None:
    """Идемпотентно: повторный запуск не плодит дубли и не трогает существующие тарифы."""
    for tariff_id, title, price in SEED_TARIFFS:
        if db.get(models.Tariff, tariff_id) is None:
            db.add(models.Tariff(id=tariff_id, title=title, price=price))
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """При старте: создаёт таблицы и заполняет справочник тарифов."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_tariffs(db)
    yield


app = FastAPI(title="Kvitto Payments API", lifespan=lifespan)
app.include_router(tariffs.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
