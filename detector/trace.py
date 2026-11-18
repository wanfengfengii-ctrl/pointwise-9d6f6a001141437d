from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from detector.step import advance_tick, check_entry_amount
from recording.ingest import OriginalTick
from recording.ledger import RecordingLedger


@dataclass(frozen=True)
class TraceResult:
    alarms: tuple[int, ...]
    amount: Fraction


def evaluate_ticks(ticks: Iterable[OriginalTick], threshold: object, entry: object = 0) -> TraceResult:
    """Evaluate parsed ticks in the supplied order."""
    amount = check_entry_amount(threshold, entry)
    alarms = []
    for tick in ticks:
        step = advance_tick(threshold, amount, tick.deviation)
        amount = step.amount
        if step.alarm:
            alarms.append(tick.number)
    return TraceResult(tuple(alarms), amount)


def preview(ledger: RecordingLedger, recording_id: str, entry: object = 0) -> TraceResult:
    recording = ledger.get_sealed(recording_id)
    return evaluate_ticks(recording.ticks, recording.assignment.plan.threshold, entry)
