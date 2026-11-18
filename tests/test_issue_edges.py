import json
import sqlite3
from contextlib import closing
from fractions import Fraction

from archive.commit import ArchiveStore
from archive.export import export_report
from archive.read import read_report
from plans.assignments import register_plan
from recording.sequence import TickCoverage
from reports.issue import issue_report
from tests.support import ProjectCase, independent_recurrence, supplied_handoffs


class IssueEdgeTests(ProjectCase):
    def test_provided_response(self):
        assignment = self.station.assignment
        self.station.detach()
        day, night = supplied_handoffs()
        issued = issue_report(self.archive, assignment, TickCoverage(1, 3), (night, day))
        self.assertEqual(issued.result.alarms, (2,))
        self.assertEqual(issued.result.amount, Fraction(0))
        self.assertEqual(tuple(ref.evidence_id for ref in issued.result.references),
                         ('provided-white', 'provided-night'))
        self.assertEqual(read_report(self.archive, issued.report_id).report, issued)

    def test_floor_reset_oracle(self):
        deviations = (-3, Fraction(1, 2), Fraction(9, 2), 6, -1, Fraction(13, 4))
        self.station.seal('day', 11, deviations[:2])
        self.station.seal('night', 13, deviations[2:])
        day = self.handoff(self.station, 'day', 'oracle-day', 11, 12)
        night = self.handoff(self.station, 'night', 'oracle-night', 13, 16)
        assignment = self.station.assignment
        self.station.detach()
        expected = independent_recurrence(11, deviations, 5)
        self.assertEqual(expected, ((13, 14), Fraction(13, 4)))
        issued = issue_report(self.archive, assignment, TickCoverage(11, 16),
                              (night.read_bytes(), day.read_bytes()))
        self.assertEqual((issued.result.alarms, issued.result.amount), expected)
        received = read_report(self.archive, issued.report_id).report
        self.assertEqual((received.result.alarms, received.result.amount), expected)

    def test_after_report_insert(self):
        day, night = supplied_handoffs()
        coverage = TickCoverage(1, 3)
        old = issue_report(self.archive, self.station.assignment, coverage, (day, night))
        with closing(sqlite3.connect(self.archive.path)) as db, db:
            db.execute('''
                CREATE TRIGGER fail_before_receipt BEFORE INSERT ON receipts
                WHEN EXISTS (SELECT 1 FROM reports WHERE report_id = NEW.report_id)
                BEGIN SELECT RAISE(ABORT, 'failed after report insert'); END
            ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'failed after report insert'):
            issue_report(self.archive, self.station.assignment, coverage, (day, night))
        self.archive = ArchiveStore(self.archive.path)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_report(self.archive, old.report_id).report, old)

    def test_original_number(self):
        self.station.seal('roll', 1, (4, 2, -1))
        whole = self.handoff(self.station, 'roll', 'whole', 1, 3).read_bytes()
        white = self.handoff(self.station, 'roll', 'white', 1, 1).read_bytes()
        night = self.handoff(self.station, 'roll', 'night', 2, 3).read_bytes()
        coverage = TickCoverage(1, 3)
        first = issue_report(self.archive, self.station.assignment, coverage, (whole,))
        second = issue_report(self.archive, self.station.assignment, coverage, (night, white))
        self.assertEqual((first.result.alarms, first.result.amount), (second.result.alarms, second.result.amount))
        self.assertNotEqual(first.result.references, second.result.references)
        self.assertNotEqual(first.receipt, second.receipt)
        register_plan(self.station.path, 'next-roll', 'surface', 'r2', 'du', 6)
        self.station.detach()
        reopened = ArchiveStore(self.archive.path)
        self.assertEqual(self.archive_counts(), (2, 2))
        for issued, identifiers in ((first, ['whole']), (second, ['white', 'night'])):
            with self.subTest(report_id=issued.report_id):
                self.assertEqual(read_report(reopened, issued.report_id).report, issued)
                target = self.transfer / f'report-{issued.report_id}.json'
                delivery = export_report(reopened, issued.report_id, target)
                self.assertEqual(delivery.payload, target.read_bytes())
                payload = json.loads(delivery.payload)
                self.assertEqual(payload['report_id'], issued.report_id)
                self.assertEqual(payload['result']['alarms'], [2])
                self.assertEqual(payload['result']['amount'], [0, 1])
                self.assertEqual(payload['result']['plan']['revision'], 'r1')
                self.assertEqual([ref['evidence_id'] for ref in payload['result']['references']], identifiers)
                self.assertEqual(payload['receipt'], {'report_id': issued.report_id,
                                                      'receipt_id': issued.receipt.receipt_id})

    def test_unknown_number(self):
        issued = issue_report(self.archive, self.station.assignment, TickCoverage(1, 3), supplied_handoffs())
        unknown = 'absent-report'
        lookup = read_report(self.archive, unknown)
        self.assertEqual(lookup.requested_id, unknown)
        self.assertFalse(lookup.found)
        self.assertIsNone(lookup.report)
        target = self.transfer / 'absent.json'
        with self.assertRaises(KeyError):
            export_report(self.archive, unknown, target)
        self.assertFalse(target.exists())
        self.assertEqual(read_report(self.archive, issued.report_id).report, issued)
