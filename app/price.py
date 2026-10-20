PROMOS: dict[str, int] = {"KVITTO10": 10}
INSTALLMENT_TERMS = (3, 6, 12)

class UnknownPromo(ValueError):
    """Промокод отсутствует в справочнике PROMOS."""


def apply_promo(price: int, code: str | None) -> tuple[int, int]:
    """Возвращает (discount, amount) в копейках.

    Скидка считается целочисленно и округляется вниз. Для текущих цен
    10% делится нацело, так что округления на практике нет.
    """
    if code is None:
        return 0, price
    percent = PROMOS.get(code.strip().upper())
    if percent is None:
        raise UnknownPromo(code)
    discount = price * percent // 100
    return discount, price - discount


def build_schedule(amount: int, months: int) -> list[int]:
    """Делит amount на months платежей; лишние копейки уходят в первые платежи."""
    base, remainder = divmod(amount, months)
    return [base + 1 if i < remainder else base for i in range(months)]
