import hashlib
import hmac
import json
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Payment
from app.schemas import WebhookIn
from app.statuses import Status, can_transition

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _signature_ok(secret: str, raw_body: bytes, signature: str | None) -> bool:
    """Проверяет HMAC-SHA256 подпись тела запроса (hex в заголовке X-Signature)."""
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), (signature or "").encode())


def _change_status(
    db: Session, payment_id: str, new: Status
) -> Literal["ok", "not_found", "invalid"]:
    """Меняет статус платежа по правилам графа"""
    payment = db.get(Payment, payment_id)
    payment = db.get(Payment, payment_id)
    if payment is None:
        return "not_found"
    current = Status(payment.status)
    if not can_transition(current, new):
        return "invalid"
    result = db.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == current.value)
        .values(status=new.value)
    )
    db.commit()
    return "ok" if result.rowcount == 1 else "invalid"


@router.post("/bank")
async def bank_webhook(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """Вебхук банка: подпись (если задан WEBHOOK_SECRET), смена статуса платежа."""
    raw = await request.body()
    secret = os.getenv("WEBHOOK_SECRET")
    if secret and not _signature_ok(secret, raw, request.headers.get("X-Signature")):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        data = WebhookIn.model_validate_json(raw)
    except ValidationError as exc:
        detail = json.loads(exc.json(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from None

    outcome = await run_in_threadpool(_change_status, db, data.payment_id, data.status)
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="payment not found")
    if outcome == "invalid":
        return JSONResponse(status_code=409, content={"error": "invalid_transition"})
    return JSONResponse(status_code=200, content={"result": "ok"})
