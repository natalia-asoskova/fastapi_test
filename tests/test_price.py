import pytest

from app.price import UnknownPromo, apply_promo, build_schedule


def test_example_from_assignment():
    assert build_schedule(1_990_000, 3) == [663_334, 663_333, 663_333]


@pytest.mark.parametrize("amount", [1, 7, 100_001, 1_790_000, 2_691_000, 9_999_999])
@pytest.mark.parametrize("months", [3, 6, 12])
def test_schedule_sums_exactly(amount, months):
    schedule = build_schedule(amount, months)
    assert len(schedule) == months
    assert sum(schedule) == amount
    assert schedule == sorted(schedule, reverse=True)
    assert max(schedule) - min(schedule) <= 1


def test_promo_is_case_insensitive_and_integer():
    assert apply_promo(1_990_000, "kvitto10") == (199_000, 1_791_000)
    assert apply_promo(1_990_000, " KvItTo10 ") == (199_000, 1_791_000)
    assert isinstance(apply_promo(990_000, "KVITTO10")[0], int)


def test_no_promo():
    assert apply_promo(990_000, None) == (0, 990_000)


def test_unknown_promo():
    with pytest.raises(UnknownPromo):
        apply_promo(990_000, "NOPE")
