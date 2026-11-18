from collections.abc import Iterable
from dataclasses import dataclass

from recording.ingest import OriginalTick


@dataclass(frozen=True)
class TickCoverage:
    first: int
    last: int

    def __post_init__(self):
        if type(self.first) is not int or type(self.last) is not int:
            raise ValueError('coverage bounds must be integer original ticks')
        if self.first > self.last:
            raise ValueError('empty tick coverage')

    def contains(self, tick: int) -> bool:
        return type(tick) is int and self.first <= tick <= self.last


def check_contiguous(ticks: Iterable[OriginalTick], coverage: TickCoverage) -> tuple[OriginalTick, ...]:
    ordered = tuple(sorted(ticks, key=lambda tick: tick.number))
    expected = coverage.first
    for tick in ordered:
        number = tick.number
        if not coverage.contains(number):
            raise ValueError(f'tick {number} lies outside recording coverage')
        if number < expected:
            raise ValueError(f'duplicate tick {number}')
        if number > expected:
            raise ValueError(f'missing tick {expected}')
        expected += 1
    if expected <= coverage.last:
        raise ValueError(f'missing tick {expected}')
    return ordered
