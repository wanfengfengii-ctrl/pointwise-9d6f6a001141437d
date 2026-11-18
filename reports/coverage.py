from collections.abc import Iterable

from evidence.binding import SegmentEvidence
from recording.sequence import TickCoverage


class CoverageError(ValueError):
    pass


def order_complete_coverage(segments: Iterable[SegmentEvidence],
                            coverage: TickCoverage) -> tuple[SegmentEvidence, ...]:
    ordered = tuple(sorted(segments, key=lambda segment: segment.binding.coverage.first))
    expected = coverage.first
    for segment in ordered:
        section = segment.binding.coverage
        if section.first < coverage.first or section.last > coverage.last:
            raise CoverageError(f'segment {segment.evidence_id} lies outside roll coverage')
        if section.first < expected:
            raise CoverageError(f'overlap at original tick {section.first}')
        if section.first > expected:
            raise CoverageError(f'coverage gap at original tick {expected}')
        expected = section.last + 1
    if expected <= coverage.last:
        raise CoverageError(f'terminal coverage gap at original tick {expected}')
    return ordered
