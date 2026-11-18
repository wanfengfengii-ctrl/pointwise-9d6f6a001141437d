from collections.abc import Iterable, Mapping

from plans.assignments import resolve_assignment
from recording.ingest import OriginalTick, parse_ticks
from recording.ledger import RecordingLedger, SealedRecording
from recording.sequence import TickCoverage


def seal_recording(ledger: RecordingLedger, recording_id: str, roll_id: str,
                   coverage: TickCoverage, rows: Iterable[Mapping]) -> SealedRecording:
    assignment = resolve_assignment(ledger.path, roll_id)
    ticks = parse_ticks(rows, assignment)
    return ledger.save_sealed(SealedRecording(recording_id, assignment, coverage, ticks))


def select_ticks(recording: SealedRecording, coverage: TickCoverage) -> tuple[OriginalTick, ...]:
    if not recording.coverage.contains(coverage.first) or not recording.coverage.contains(coverage.last):
        raise ValueError('segment lies outside sealed recording')
    start = coverage.first - recording.coverage.first
    stop = coverage.last - recording.coverage.first + 1
    return recording.ticks[start:stop]
