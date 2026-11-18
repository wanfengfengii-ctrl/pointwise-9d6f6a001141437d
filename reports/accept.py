from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from evidence.binding import SegmentEvidence
from evidence.codec import decode_segment, encode_segment
from plans.assignments import RollAssignment
from plans.revisions import check_identifier
from recording.sequence import TickCoverage
from reports.coverage import order_complete_coverage


@dataclass(frozen=True)
class SegmentReference:
    evidence_id: str
    digest: str

    def __post_init__(self):
        check_identifier(self.evidence_id, 'evidence ID')
        if not isinstance(self.digest, str) or len(self.digest) != 64:
            raise ValueError('invalid segment content digest')
        if any(character not in '0123456789abcdef' for character in self.digest):
            raise ValueError('invalid segment content digest')


@dataclass(frozen=True)
class AcceptedSegments:
    assignment: RollAssignment
    coverage: TickCoverage
    segments: tuple[SegmentEvidence, ...]
    references: tuple[SegmentReference, ...]


def accept_segments(assignment: RollAssignment, coverage: TickCoverage,
                    payloads: Iterable[bytes]) -> AcceptedSegments:
    segments = []
    for payload in payloads:
        evidence = decode_segment(payload)
        if evidence.binding.roll_id != assignment.roll_id:
            raise ValueError(f'roll mismatch in evidence {evidence.evidence_id}')
        if evidence.binding.plan != assignment.plan:
            raise ValueError(f'plan revision mismatch in evidence {evidence.evidence_id}')
        segments.append(evidence)
    ordered = order_complete_coverage(segments, coverage)
    if len({segment.evidence_id for segment in ordered}) != len(ordered):
        raise ValueError('duplicate evidence ID in the specified collection')
    references = tuple(
        SegmentReference(segment.evidence_id, sha256(encode_segment(segment)).hexdigest())
        for segment in ordered
    )
    return AcceptedSegments(assignment, coverage, ordered, references)
