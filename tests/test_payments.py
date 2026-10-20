import pytest
from sqlalchemy import func, select

from app.models import Payment
from tests.conftest import create_payment


def test_tariffs(client):
    resp = client.get("/tariffs")
    assert resp.status_code == 200
    assert {(t["id"], t["price"]) for t in resp.json()} == {
        ("basic", 990_000),
        ("standard", 1_990_000),
        ("premium", 2_990_000),
    }


@pytest.mark.parametrize(
    ("tariff", "price"), [("basic", 990_000), ("standard", 1_990_000), ("premium", 2_990_000)]
)
def test_amount_without_promo(client, tariff, price):
    body = create_payment(client, tariff_id=tariff).json()
    assert (body["amount"], body["discount"]) == (price, 0)
    assert body["status"] == "pending"
    assert body["schedule"] is None


@pytest.mark.parametrize("code", ["KVITTO10", "kvitto10", "Kvitto10"])
def test_amount_with_promo_any_case(client, code):
    resp = create_payment(client, promo_code=code)
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 1_791_000
    assert body["discount"] == 199_000


def test_unknown_promo_returns_422(client, session_factory):
    resp = create_payment(client, promo_code="WRONG")
    assert resp.status_code == 422
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0


@pytest.mark.parametrize("months", [3, 6, 12])
@pytest.mark.parametrize("promo", [None, "KVITTO10"])
def test_installment_schedule_sums_to_amount(client, months, promo):
    body = create_payment(
        client, method="installment", installment_months=months, promo_code=promo
    ).json()
    assert len(body["schedule"]) == months
    assert sum(body["schedule"]) == body["amount"]
    assert body["installment_months"] == months


def test_installment_example_from_assignment(client):
    body = create_payment(client, method="installment", installment_months=3).json()
    assert body["schedule"] == [663_334, 663_333, 663_333]


@pytest.mark.parametrize(
    "overrides",
    [
        {"method": "installment"},
        {"method": "installment", "installment_months": 5},
        {"method": "card", "installment_months": 3},
        {"method": "cash"},
        {"email": "not-an-email"},
        {"tariff_id": "nope"},
    ],
)
def test_validation_errors_return_422(client, overrides):
    assert create_payment(client, **overrides).status_code == 422


def test_idempotency_key_does_not_create_duplicate(client, session_factory):
    headers = {"Idempotency-Key": "abc-123"}
    first = create_payment(client, headers=headers)
    second = create_payment(client, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_different_keys_create_different_payments(client):
    a = create_payment(client, headers={"Idempotency-Key": "k1"})
    b = create_payment(client, headers={"Idempotency-Key": "k2"})
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


def test_without_key_every_request_creates_payment(client, session_factory):
    create_payment(client)
    create_payment(client)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 2


def test_get_payment(client):
    created = create_payment(client, email="x@example.com").json()
    resp = client.get(f"/payments/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_get_missing_payment_returns_404(client):
    assert client.get("/payments/does-not-exist").status_code == 404


def test_list_filters(client):
    a = create_payment(client, email="a@example.com").json()
    create_payment(client, email="b@example.com")
    client.post("/webhooks/bank", json={"payment_id": a["id"], "status": "succeeded"})

    assert len(client.get("/payments").json()) == 2
    by_email = client.get("/payments", params={"email": "a@example.com"}).json()
    assert [p["id"] for p in by_email] == [a["id"]]
    by_status = client.get("/payments", params={"status": "succeeded"}).json()
    assert [p["id"] for p in by_status] == [a["id"]]
