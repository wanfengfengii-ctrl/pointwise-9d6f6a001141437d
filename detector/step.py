from dataclasses import dataclass
from fractions import Fraction

from plans.thresholds import parse_rational, parse_threshold


@dataclass(frozen=True)
class StepResult:
    amount: Fraction
    alarm: bool


def check_entry_amount(threshold: object, entry: object) -> Fraction:
    limit = parse_threshold(threshold)
    amount = parse_rational(entry)
    if not 0 <= amount < limit:
        raise ValueError('entry amount must lie in [0, threshold)')
    return amount


def advance_tick(threshold: object, entry: object, deviation: object) -> StepResult:
    limit = parse_threshold(threshold)
    amount = check_entry_amount(limit, entry)
    candidate = max(Fraction(0), amount + parse_rational(deviation))
    if candidate >= limit:
        return StepResult(Fraction(0), True)
    return StepResult(candidate, False)
