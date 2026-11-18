from hashlib import sha256

from archive.read import read_report
from recording.sequence import TickCoverage
from reports.accept import accept_segments
from reports.coverage import CoverageError
from reports.issue import issue_report
from tests.support import ProjectCase


class HandoffEdgeTests(ProjectCase):
    def test_terminal_gap(self):
        self.station.seal('roll', 1, (0, 0, 5))
        prefix = self.handoff(self.station, 'roll', 'prefix', 1, 2).read_bytes()
        complete = self.handoff(self.station, 'roll', 'complete', 1, 3).read_bytes()
        with self.assertRaisesRegex(CoverageError, 'terminal coverage gap at original tick 3'):
            issue_report(self.archive, self.station.assignment, TickCoverage(1, 3), (prefix,))
        self.assertEqual(self.archive_counts(), (0, 0))
        report = issue_report(self.archive, self.station.assignment, TickCoverage(1, 3), (complete,))
        self.assertEqual(report.result.alarms, (3,))
        self.assertEqual(report.result.amount, 0)

    def test_equal_settings_other_revision(self):
        station_r2 = self.new_station('station-r2', revision='r2')
        self.station.seal('day', 1, (4,))
        station_r2.seal('night', 2, (2, -1))
        day = self.handoff(self.station, 'day', 'day-r1', 1, 1).read_bytes()
        night = self.handoff(station_r2, 'night', 'night-r2', 2, 3).read_bytes()
        for operation in (accept_segments,):
            with self.assertRaisesRegex(ValueError, 'plan revision mismatch'):
                operation(self.station.assignment, TickCoverage(1, 3), (day, night))
        with self.assertRaisesRegex(ValueError, 'plan revision mismatch'):
            issue_report(self.archive, self.station.assignment, TickCoverage(1, 3), (day, night))
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_explicit_selection(self):
        self.station.seal('day', 1, (4,))
        self.station.seal('night', 2, (2, -1))
        self.station.seal('unused', 2, (0, 1))
        day = self.handoff(self.station, 'day', 'day-selected', 1, 1).read_bytes()
        night = self.handoff(self.station, 'night', 'night-selected', 2, 3).read_bytes()
        unused = self.handoff(self.station, 'unused', 'night-unused', 2, 3)
        self.assertTrue(unused.is_file())
        coverage = TickCoverage(1, 3)
        accepted = accept_segments(self.station.assignment, coverage, (night, day))
        self.assertEqual(tuple(segment.evidence_id for segment in accepted.segments),
                         ('day-selected', 'night-selected'))
        report = issue_report(self.archive, self.station.assignment, coverage, (night, day))
        self.assertEqual(tuple((ref.evidence_id, ref.digest) for ref in report.result.references),
                         (('day-selected', sha256(day).hexdigest()), ('night-selected', sha256(night).hexdigest())))
        self.assertEqual(report.result.alarms, (2,))
        self.assertEqual(read_report(self.archive, report.report_id).report, report)
