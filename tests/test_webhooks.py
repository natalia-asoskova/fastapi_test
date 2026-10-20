import hashlib
import hmac
import json

import pytest

from tests.conftest import create_payment


def webhook(client, payment_id, status, **kwargs):
    body = {"payment_id": payment_id, "status": status}
    return client.post("/webhooks/bank", json=body, **kwargs)


def status_of(client, payment_id):
    return client.get(f"/payments/{payment_id}").json()["status"]


@pytest.mark.parametrize(
    ("path", "final"),
    [
        (["succeeded"], "succeeded"),
        (["failed"], "failed"),
        (["succeeded", "refunded"], "refunded"),
    ],
)
def test_allowed_transitions(client, path, final):
    pid = create_payment(client).json()["id"]
    for step in path:
        resp = webhook(client, pid, step)
        assert resp.status_code == 200
        assert resp.json() == {"result": "ok"}
    assert status_of(client, pid) == final


@pytest.mark.parametrize(
    ("setup", "forbidden"),
    [
        ([], "refunded"),  # pending -> refunded
        ([], "pending"),  # pending -> pending
        (["succeeded"], "failed"),
        (["succeeded"], "pending"),
        (["succeeded"], "succeeded"),  # повтор того же статуса
        (["failed"], "succeeded"),
        (["failed"], "refunded"),
        (["succeeded", "refunded"], "succeeded"),
    ],
)
def test_forbidden_transition_returns_409_and_keeps_status(client, setup, forbidden):
    pid = create_payment(client).json()["id"]
    for step in setup:
        webhook(client, pid, step)
    before = status_of(client, pid)

    resp = webhook(client, pid, forbidden)

    assert resp.status_code == 409
    assert resp.json() == {"error": "invalid_transition"}
    assert status_of(client, pid) == before


def test_webhook_for_missing_payment_returns_404(client):
    assert webhook(client, "does-not-exist", "succeeded").status_code == 404


def test_webhook_unknown_status_returns_422(client):
    pid = create_payment(client).json()["id"]
    assert webhook(client, pid, "exploded").status_code == 422
    assert status_of(client, pid) == "pending"


def _signed(secret: str, payload: dict) -> tuple[bytes, dict]:
    raw = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Signature": sig, "Content-Type": "application/json"}


def test_signature_valid(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cret")
    pid = create_payment(client).json()["id"]
    raw, headers = _signed("s3cret", {"payment_id": pid, "status": "succeeded"})

    assert client.post("/webhooks/bank", content=raw, headers=headers).status_code == 200
    assert status_of(client, pid) == "succeeded"


@pytest.mark.parametrize("signature", ["deadbeef", "", None])
def test_signature_invalid_returns_401_and_keeps_status(client, monkeypatch, signature):
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cret")
    pid = create_payment(client).json()["id"]
    raw, headers = _signed("s3cret", {"payment_id": pid, "status": "succeeded"})
    if signature is None:
        headers.pop("X-Signature")
    else:
        headers["X-Signature"] = signature

    assert client.post("/webhooks/bank", content=raw, headers=headers).status_code == 401
    assert status_of(client, pid) == "pending"
