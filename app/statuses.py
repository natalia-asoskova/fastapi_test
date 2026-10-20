from enum import StrEnum


class Status(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class Method(StrEnum):
    card = "card"
    sbp = "sbp"
    installment = "installment"

ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.pending: {Status.succeeded, Status.failed},
    Status.succeeded: {Status.refunded},
}


def can_transition(current: Status, new: Status) -> bool:
    """True, если переход current → new разрешён в ALLOWED_TRANSITIONS."""
    return new in ALLOWED_TRANSITIONS.get(current, set())
