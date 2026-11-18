from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from plans.thresholds import parse_rational, parse_threshold


@dataclass(frozen=True)
class RationalInterval:
    start: Fraction
    stop: Fraction

    def __post_init__(self):
        start = parse_rational(self.start)
        stop = parse_rational(self.stop)
        if start >= stop:
            raise ValueError('response interval must be nonempty')
        object.__setattr__(self, 'start', start)
        object.__setattr__(self, 'stop', stop)

    def contains(self, value: Fraction) -> bool:
        return self.start <= value < self.stop


def partition_at(interval: RationalInterval, points: Iterable[Fraction]) -> tuple[RationalInterval, ...]:
    cuts = {parse_rational(point) for point in points}
    interior = sorted(point for point in cuts if interval.start < point < interval.stop)
    ends = [interval.start, *interior, interval.stop]
    return tuple(RationalInterval(left, right) for left, right in zip(ends, ends[1:]))


def check_partition(intervals: Iterable[RationalInterval], threshold: object) -> None:
    limit = parse_threshold(threshold)
    expected = Fraction(0)
    for interval in intervals:
        if interval.start != expected or interval.stop > limit:
            raise ValueError('response intervals must form an ordered partition of [0, threshold)')
        expected = interval.stop
    if expected != limit:
        raise ValueError('response does not cover [0, threshold)')
