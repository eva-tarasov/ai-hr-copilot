"""Allowed S04 state transitions; terminal states have no outgoing edges."""

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"running", "interrupted"}),
    "running": frozenset({"completed", "completed_with_errors", "failed", "interrupted"}),
    "completed": frozenset(),
    "completed_with_errors": frozenset(),
    "failed": frozenset(),
    "interrupted": frozenset(),
}

DOCUMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"running", "failed", "interrupted"}),
    "running": frozenset({"completed", "failed", "interrupted"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "interrupted": frozenset(),
}


def require_transition(transitions: dict[str, frozenset[str]], current: str, target: str) -> None:
    if target not in transitions.get(current, frozenset()):
        raise ValueError(f"Invalid state transition: {current} -> {target}")
