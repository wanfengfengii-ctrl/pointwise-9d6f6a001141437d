from fractions import Fraction

from detector.trace import preview
from plans.assignments import register_plan, resolve_assignment
from recording.segments import seal_recording
from recording.sequence import TickCoverage
from tests.support import ProjectCase, record_count, rows_for


class PlanTests(ProjectCase):
    def test_same_revision_conflict(self):
        with self.assertRaisesRegex(ValueError, 'conflicting fixed plan revision'):
            register_plan(self.station.path, 'roll-B', 'surface', 'r1', 'du', 6)
        self.assertEqual(resolve_assignment(self.station.path, 'roll-A').plan.threshold, Fraction(5))
        with self.assertRaises(KeyError):
            resolve_assignment(self.station.path, 'roll-B')
        self.assertEqual(record_count(self.station.path, 'plan_revisions'), 1)

    def test_repeat_initialization(self):
        recording = self.station.seal('day', 10, (4,))
        self.station.publish('day', 'existing', 10, 10)
        self.station.initialize()
        same = register_plan(self.station.path, 'roll-A', 'surface', 'r1', 'du', '10/2')
        self.assertEqual(same, self.station.assignment)
        self.assertEqual(self.station.recordings.get_sealed('day'), recording)
        self.assertEqual(self.station.segments.get_published('existing').binding.plan.threshold, Fraction(5))
        self.assertEqual(record_count(self.station.path, 'roll_assignments'), 1)
        self.assertEqual(record_count(self.station.path, 'plan_revisions'), 1)

    def test_invalid_registration(self):
        for unit, threshold in (('unknown', 5), ('du', 0), ('du', -3), ('du', '4/0'), ('du', 1.25)):
            with self.subTest(unit=unit, threshold=threshold):
                with self.assertRaises(ValueError):
                    register_plan(self.station.path, 'roll-B', 'surface', 'r2', unit, threshold)
                self.assertEqual(record_count(self.station.path, 'plan_revisions'), 1)
                self.assertEqual(record_count(self.station.path, 'roll_assignments'), 1)
        with self.assertRaisesRegex(ValueError, 'already bound'):
            register_plan(self.station.path, 'roll-A', 'surface', 'r2', 'du', 6)
        self.assertEqual(record_count(self.station.path, 'plan_revisions'), 1)
        self.assertEqual(resolve_assignment(self.station.path, 'roll-A'), self.station.assignment)


class RecordingTests(ProjectCase):
    def test_missing_original_tick(self):
        rows = rows_for(self.station.assignment, ((1, 4), (3, -1)))
        with self.assertRaisesRegex(ValueError, 'missing tick 2'):
            seal_recording(self.station.recordings, 'gap', 'roll-A', TickCoverage(1, 3), rows)
        with self.assertRaises(KeyError):
            self.station.publish('gap', 'invalid', 1, 3)
        self.assertEqual(record_count(self.station.path, 'recordings'), 0)
        self.assertEqual(record_count(self.station.path, 'published_segments'), 0)

    def test_duplicate_masks_gap(self):
        rows = rows_for(self.station.assignment, ((1, 4), (1, 2), (3, -1)))
        with self.assertRaisesRegex(ValueError, 'duplicate tick 1'):
            seal_recording(self.station.recordings, 'duplicate', 'roll-A', TickCoverage(1, 3), rows)
        self.assertEqual(record_count(self.station.path, 'recordings'), 0)
        with self.assertRaises(KeyError):
            self.station.publish('duplicate', 'invalid', 1, 3)

    def test_exact_ticks(self):
        rows = rows_for(self.station.assignment, ((42, '1/3'), (40, '-3/7'), (41, [0, 1])))
        saved = seal_recording(self.station.recordings, 'exact', 'roll-A', TickCoverage(40, 42), rows)
        fixed = self.station.recordings.get_sealed('exact')
        self.assertEqual(fixed, saved)
        self.assertEqual(tuple((tick.number, tick.deviation) for tick in fixed.ticks),
                         ((40, Fraction(-3, 7)), (41, Fraction(0)), (42, Fraction(1, 3))))
        new_rows = [dict(row) for row in rows]
        new_rows[0]['revision'] = 'other'
        with self.assertRaisesRegex(ValueError, 'reading identity differs'):
            seal_recording(self.station.recordings, 'wrong', 'roll-A', TickCoverage(40, 42), new_rows)
        self.assertEqual(record_count(self.station.path, 'recordings'), 1)

    def test_floor_and_reset(self):
        self.station.seal('day', 1, (-1, 5, 6, 2))
        result = preview(self.station.recordings, 'day')
        self.assertEqual(result.alarms, (2, 3))
        self.assertEqual(result.amount, Fraction(2))

    def test_invalid_entry(self):
        self.station.seal('day', 1, (0,))
        for entry in (Fraction(-1, 10), Fraction(5)):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, 'entry amount'):
                preview(self.station.recordings, 'day', entry)
        with self.assertRaises(KeyError):
            preview(self.station.recordings, 'unknown')
        self.assertEqual(record_count(self.station.path, 'recordings'), 1)
