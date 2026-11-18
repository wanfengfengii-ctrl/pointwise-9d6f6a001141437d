import sqlite3
from contextlib import closing
from fractions import Fraction

from archive.commit import ArchiveStore
from archive.read import read_report
from plans.assignments import register_plan, resolve_assignment
from recording.sequence import TickCoverage
from reports.issue import issue_report
from tests.support import ProjectCase


class ArchiveTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.station.seal('roll', 1, (4, 2, -1))
        self.payload = self.handoff(self.station, 'roll', 'whole', 1, 3).read_bytes()
        self.coverage = TickCoverage(1, 3)

    def test_issue_rollback(self):
        existing = issue_report(self.archive, self.station.assignment, self.coverage, (self.payload,))
        with closing(sqlite3.connect(self.archive.path)) as db, db:
            db.execute('''
                CREATE TABLE deferred_guard (
                    report_id TEXT REFERENCES reports(report_id) DEFERRABLE INITIALLY DEFERRED
                )
            ''')
            db.execute('''
                CREATE TRIGGER fail_at_commit AFTER INSERT ON receipts
                BEGIN INSERT INTO deferred_guard VALUES ('absent-report'); END
            ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
            issue_report(self.archive, self.station.assignment, self.coverage, (self.payload,))
        self.archive = ArchiveStore(self.archive.path)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_report(self.archive, existing.report_id).report, existing)

    def test_fixed_report_after_reopen(self):
        issued = issue_report(self.archive, self.station.assignment, self.coverage, (self.payload,))
        successor = register_plan(self.station.path, 'next-roll', 'surface', 'r2', 'du', 6)
        self.assertEqual(successor.plan.threshold, Fraction(6))
        self.assertEqual(resolve_assignment(self.station.path, 'roll-A'), self.station.assignment)
        reopened = ArchiveStore(self.archive.path)
        reopened.initialize()
        lookup = read_report(reopened, issued.report_id)
        self.assertTrue(lookup.found)
        self.assertEqual(lookup.report, issued)
        self.assertEqual(lookup.report.result.alarms, (2,))
        self.assertEqual(lookup.report.result.amount, Fraction(0))
        self.assertEqual(lookup.report.result.assignment.plan.threshold, Fraction(5))
