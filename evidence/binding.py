from dataclasses import dataclass

from detector.response import SegmentResponse, validate_response
from plans.revisions import PlanRevision, check_identifier
from recording.ledger import SealedRecording
from recording.sequence import TickCoverage


@dataclass(frozen=True)
class SegmentBinding:
    roll_id: str
    plan: PlanRevision
    recording_id: str
    coverage: TickCoverage

    def __post_init__(self):
        check_identifier(self.roll_id, 'roll ID')
        check_identifier(self.recording_id, 'recording ID')
        if not isinstance(self.plan, PlanRevision) or not isinstance(self.coverage, TickCoverage):
            raise ValueError('segment binding requires a fixed plan and coverage')


@dataclass(frozen=True)
class SegmentEvidence:
    evidence_id: str
    binding: SegmentBinding
    response: SegmentResponse


def make_binding(recording: SealedRecording, coverage: TickCoverage) -> SegmentBinding:
    if not recording.coverage.contains(coverage.first) or not recording.coverage.contains(coverage.last):
        raise ValueError('segment binding lies outside sealed recording')
    return SegmentBinding(recording.assignment.roll_id, recording.assignment.plan,
                          recording.recording_id, coverage)


def validate_binding(evidence: SegmentEvidence) -> None:
    check_identifier(evidence.evidence_id, 'evidence ID')
    binding = evidence.binding
    response = evidence.response
    if response.threshold != binding.plan.threshold:
        raise ValueError('response threshold differs from the fixed plan')
    validate_response(response)
    for piece in response.pieces:
        if any(not binding.coverage.contains(number) for number in piece.alarms):
            raise ValueError('response alarm lies outside segment coverage')
