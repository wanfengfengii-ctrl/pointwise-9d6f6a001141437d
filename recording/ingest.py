from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from plans.assignments import RollAssignment
from plans.thresholds import parse_rational
from plans.units import parse_unit


@dataclass(frozen=True)
class OriginalTick:
    number: int
    deviation: Fraction

    def __post_init__(self):
        if type(self.number) is not int:
            raise ValueError('original tick must be an integer')
        object.__setattr__(self, 'deviation', parse_rational(self.deviation))


def parse_ticks(rows: Iterable[Mapping], assignment: RollAssignment) -> tuple[OriginalTick, ...]:
    plan = assignment.plan
    expected_identity = (assignment.roll_id, plan.plan_id, plan.revision, plan.unit)
    ticks = []
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise ValueError(f'reading {position} must be a mapping')
        try:
            identity = (row['roll_id'], row['plan_id'], row['revision'], parse_unit(row['unit']))
            if identity != expected_identity:
                raise ValueError('reading identity differs from the fixed roll assignment')
            ticks.append(OriginalTick(row['tick'], row['deviation']))
        except KeyError as exc:
            raise ValueError(f'reading {position} is missing {exc.args[0]}') from exc
        except ValueError as exc:
            raise ValueError(f'reading {position}: {exc}') from exc
    return tuple(ticks)
