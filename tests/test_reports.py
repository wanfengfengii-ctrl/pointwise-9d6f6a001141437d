from fractions import Fraction

from archive.read import read_report
from recording.sequence import TickCoverage
from reports.issue import issue_report
from tests.support import ProjectCase, independent_recurrence


class ReportTests(ProjectCase):
    def test_bad_coverage(self):
        self.station.seal('roll', 1, (4, 2, -1))
        first = self.handoff(self.station, 'roll', 'first', 1, 1).read_bytes()
        last = self.handoff(self.station, 'roll', 'last', 3, 3).read_bytes()
        overlapping = self.handoff(self.station, 'roll', 'overlap', 1, 3).read_bytes()
        other_roll = self.new_station('other-roll', roll_id='roll-B')
        other_plan = self.new_station('other-plan', revision='r2', threshold=6)
        other_roll.seal('side', 2, (2, -1))
        other_plan.seal('side', 2, (2, -1))
        wrong_roll = self.handoff(other_roll, 'side', 'wrong-roll', 2, 3).read_bytes()
        wrong_plan = self.handoff(other_plan, 'side', 'wrong-plan', 2, 3).read_bytes()
        for payloads, message in (
            ((first, last), 'coverage gap at original tick 2'),
            ((first, overlapping), 'overlap'),
            ((first, wrong_roll), 'roll mismatch'),
            ((first, wrong_plan), 'plan revision mismatch'),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    issue_report(self.archive, self.station.assignment, TickCoverage(1, 3), payloads)
                self.assertEqual(self.archive_counts(), (0, 0))

    def test_offline_repartition(self):
        deviations = (4, 2, -1)
        self.station.seal('roll', 1, deviations)
        partitions = (((1, 3),), ((1, 1), (2, 3)), ((1, 1), (2, 2), (3, 3)))
        groups = []
        for index, partition in enumerate(partitions):
            groups.append(tuple(self.handoff(self.station, 'roll', f'cut-{index}-{first}', first, last)
                                for first, last in partition))
        assignment = self.station.assignment
        self.station.detach()
        self.assertFalse(self.station.path.exists())
        expected = independent_recurrence(1, deviations, 5)
        self.assertEqual(expected, ((2,), Fraction(0)))
        for paths in groups:
            with self.subTest(group=[path.stem for path in paths]):
                issued = issue_report(self.archive, assignment, TickCoverage(1, 3),
                                      (path.read_bytes() for path in reversed(paths)))
                self.assertEqual((issued.result.alarms, issued.result.amount), expected)
                self.assertEqual(tuple(ref.evidence_id for ref in issued.result.references),
                                 tuple(path.stem for path in paths))
                self.assertEqual(read_report(self.archive, issued.report_id).report, issued)
        self.assertEqual(self.archive_counts(), (3, 3))
