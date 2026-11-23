"""Pure functions for learning a plant's watering rhythm from experience."""

from __future__ import annotations

# How the soil felt before watering -> ideal interval relative to the days
# that actually passed since the previous watering.
FEEDBACK_RATIO = {"moist": 1.3, "ok": 1.0, "dry": 0.75}

# strength -> (max change per vote, votes needed, out of the last n votes)
STRENGTH = {
    "gentle": (0.05, 3, 4),
    "normal": (0.10, 2, 3),
    "strong": (0.15, 1, 1),
}

INTERVAL_FACTOR_MIN, INTERVAL_FACTOR_MAX = 0.5, 2.0
AMOUNT_FACTOR_MIN, AMOUNT_FACTOR_MAX = 0.5, 1.5
DEADBAND = 0.05
MAX_VOTES = 4


def target_factor(elapsed_days: float, base_interval: float, answer: str) -> float:
    """Factor on the calculated interval that the answer suggests."""
    ideal = elapsed_days * FEEDBACK_RATIO[answer]
    return min(
        max(ideal / max(base_interval, 0.25), INTERVAL_FACTOR_MIN), INTERVAL_FACTOR_MAX
    )


# What an answer tells about the ideal interval:
#   moist -> at least this long (only ever lengthens)
#   dry   -> at most this long (only ever shortens)
#   ok / measured -> about this long (both directions)
ANSWER_KIND = {"moist": "at_least", "dry": "at_most", "ok": "about"}


def apply_vote(
    factor: float,
    target: float,
    votes: list[int],
    strength: str,
    lower: float = INTERVAL_FACTOR_MIN,
    upper: float = INTERVAL_FACTOR_MAX,
    kind: str = "about",
) -> tuple[float, list[int]]:
    """Move `factor` towards `target` once enough votes agree.

    Watering late and finding the soil very dry carries no information
    ("at most 12 days" while the interval is 8) and casts a neutral vote.
    """
    if abs(target - factor) < DEADBAND:
        direction = 0
    else:
        direction = 1 if target > factor else -1
    if (kind == "at_least" and direction < 0) or (kind == "at_most" and direction > 0):
        direction = 0
    votes = [*votes, direction][-MAX_VOTES:]
    cap, needed, window = STRENGTH.get(strength, STRENGTH["normal"])
    if direction != 0 and votes[-window:].count(direction) >= needed:
        delta = max(-cap, min(cap, 0.5 * (target - factor)))
        factor = min(max(factor + delta, lower), upper)
    return round(factor, 3), votes


def default_learning() -> dict:
    """Initial learning state of a plant."""
    return {
        "interval_factor": 1.0,
        "amount_factor": 1.0,
        "votes": [],
        "amount_votes": [],
        "history": [],
        "awaiting": None,
        "cycle": None,
        "undo": None,
    }
