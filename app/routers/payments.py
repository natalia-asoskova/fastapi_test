from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Payment, Tariff
from app.price import UnknownPromo, apply_promo, build_schedule
from app.schemas import PaymentCreate, PaymentOut
from app.statuses import Method, Status

router = APIRouter(prefix="/payments", tags=["payments"])


def _find_by_key(db: Session, key: str) -> Payment | None:
    """Ищет платёж по заголовку Idempotency-Key."""
    return db.scalar(select(Payment).where(Payment.idempotency_key == key))


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(
    body: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Payment:
    """Создаёт платёж (тариф, промо, рассрочка); идемпотентность по Idempotency-Key."""
    if idempotency_key:
        existing = _find_by_key(db, idempotency_key)
        if existing:
            response.status_code = 200
            return existing

    tariff = db.get(Tariff, body.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=422, detail="unknown tariff_id")

    try:
        discount, amount = apply_promo(tariff.price, body.promo_code)
    except UnknownPromo:
        raise HTTPException(status_code=422, detail="unknown promo_code") from None

    schedule = None
    if body.method is Method.installment:
        assert body.installment_months is not None
        schedule = build_schedule(amount, body.installment_months)

    payment = Payment(
        status=Status.pending.value,
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=body.method.value,
        installment_months=body.installment_months,
        schedule=schedule,
        email=body.email,
        idempotency_key=idempotency_key or None,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = _find_by_key(db, idempotency_key)
            if existing:
                response.status_code = 200
                return existing
        raise
    return payment


@router.get("", response_model=list[PaymentOut])
def list_payments(
    email: str | None = None,
    status: Status | None = None,
    db: Session = Depends(get_db),
) -> list[Payment]:
    """Список платежей, опционально по email и/или статусу."""
    query = select(Payment).order_by(Payment.created_at)
    if email:
        query = query.where(Payment.email == email)
    if status:
        query = query.where(Payment.status == status.value)
    return list(db.scalars(query))


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, db: Session = Depends(get_db)) -> Payment:
    """Возвращает один платёж по id или 404."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    return payment
