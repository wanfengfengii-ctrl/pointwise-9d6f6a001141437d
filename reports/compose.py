from dataclasses import dataclass
from fractions import Fraction

from detector.response import evaluate_response
from detector.step import check_entry_amount
from plans.assignments import RollAssignment
from recording.sequence import TickCoverage
from reports.accept import AcceptedSegments, SegmentReference


@dataclass(frozen=True)
class ReportResult:
    assignment: RollAssignment
    coverage: TickCoverage
    references: tuple[SegmentReference, ...]
    alarms: tuple[int, ...]
    amount: Fraction

    def __post_init__(self):
        references = tuple(self.references)
        alarms = tuple(self.alarms)
        if not references or len({reference.evidence_id for reference in references}) != len(references):
            raise ValueError('report must reference a nonempty collection of distinct evidence')
        if any(not self.coverage.contains(number) for number in alarms):
            raise ValueError('report alarm lies outside roll coverage')
        if any(left >= right for left, right in zip(alarms, alarms[1:])):
            raise ValueError('report alarms must increase strictly')
        amount = check_entry_amount(self.assignment.plan.threshold, self.amount)
        object.__setattr__(self, 'references', references)
        object.__setattr__(self, 'alarms', alarms)
        object.__setattr__(self, 'amount', amount)


def compose_report(accepted: AcceptedSegments) -> ReportResult:
    amount = Fraction(0)
    alarms = []
    for segment in accepted.segments:
        trace = evaluate_response(segment.response, 0)
        alarms.extend(trace.alarms)
        amount = trace.amount
    return ReportResult(accepted.assignment, accepted.coverage, accepted.references, tuple(alarms), amount)
