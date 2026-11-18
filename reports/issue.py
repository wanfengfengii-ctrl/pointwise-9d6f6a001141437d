from collections.abc import Iterable

from archive.commit import ArchiveStore, IssuedReport
from plans.assignments import RollAssignment
from recording.sequence import TickCoverage
from reports.accept import accept_segments
from reports.compose import compose_report


def issue_report(archive: ArchiveStore, assignment: RollAssignment,
                 coverage: TickCoverage, payloads: Iterable[bytes]) -> IssuedReport:
    accepted = accept_segments(assignment, coverage, payloads)
    result = compose_report(accepted)
    return archive.commit_issue(result)
