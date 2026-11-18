import json
import sqlite3
from contextlib import closing
from fractions import Fraction

from detector.response import evaluate_response
from detector.trace import TraceResult
from evidence.codec import decode_segment
from evidence.export import export_segment
from recording.sequence import TickCoverage
from tests.support import ProjectCase, record_count


class EvidenceTests(ProjectCase):
    def test_closed_threshold(self):
        self.station.seal('night', 2, (2, -1))
        target = self.handoff(self.station, 'night', 'night-evidence', 2, 3)
        self.station.detach()
        response = decode_segment(target.read_bytes()).response
        self.assertEqual(evaluate_response(response, Fraction(5, 2)), TraceResult((), Fraction(7, 2)))
        self.assertEqual(evaluate_response(response, 3), TraceResult((2,), Fraction(0)))
        self.assertEqual(evaluate_response(response, 4), TraceResult((2,), Fraction(0)))

    def test_publish_failure(self):
        self.station.seal('day', 1, (4, 0))
        self.station.publish('day', 'existing', 1, 1)
        with self.assertRaises(KeyError):
            self.station.publish('unsealed', 'unknown', 1, 1)
        with self.assertRaisesRegex(ValueError, 'empty tick coverage'):
            TickCoverage(2, 1)
        with self.assertRaisesRegex(ValueError, 'outside sealed recording'):
            self.station.publish('day', 'out-of-bounds', 1, 3)
        with closing(sqlite3.connect(self.station.path)) as db, db:
            db.execute('''
                CREATE TRIGGER reject_segment AFTER INSERT ON published_segments
                WHEN NEW.evidence_id = 'rejected'
                BEGIN SELECT RAISE(ABORT, 'segment write rejected'); END
            ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'segment write rejected'):
            self.station.publish('day', 'rejected', 1, 2)
        self.assertEqual(record_count(self.station.path, 'published_segments'), 1)
        with self.assertRaises(KeyError):
            self.station.segments.get_published('rejected')
        self.assertEqual(self.station.segments.get_published('existing').binding.coverage, TickCoverage(1, 1))

    def test_zero_summary_collision(self):
        self.station.seal('night-early', 2, (2, -1))
        self.station.seal('night-late', 2, (0, 1))
        early = self.handoff(self.station, 'night-early', 'early', 2, 3)
        late = self.handoff(self.station, 'night-late', 'late', 2, 3)
        self.station.detach()
        a = decode_segment(early.read_bytes()).response
        b = decode_segment(late.read_bytes()).response
        self.assertEqual(evaluate_response(a, 0), TraceResult((), Fraction(1)))
        self.assertEqual(evaluate_response(b, 0), TraceResult((), Fraction(1)))
        self.assertEqual(evaluate_response(a, 4), TraceResult((2,), Fraction(0)))
        self.assertEqual(evaluate_response(b, 4), TraceResult((3,), Fraction(0)))

    def test_exact_round_trip(self):
        self.station.seal('fractional', 20, (Fraction(5, 3), -1))
        evidence = self.station.publish('fractional', 'fractional-evidence', 20, 21)
        target = self.transfer / 'fractional.json'
        copy = self.transfer / 'fractional-copy.json'
        first = export_segment(self.station.segments, 'fractional-evidence', target)
        second = export_segment(self.station.segments, 'fractional-evidence', copy)
        self.assertEqual(first, second)
        self.assertEqual(first, target.read_bytes())
        self.assertEqual(second, copy.read_bytes())
        self.station.detach()
        restored = decode_segment(copy.read_bytes())
        self.assertEqual(restored, evidence)
        payload = json.loads(second)
        self.assertEqual(set(payload), {'version', 'evidence_id', 'binding', 'response'})
        self.assertEqual(set(payload['binding']), {'roll_id', 'plan', 'recording_id', 'coverage'})
        self.assertEqual(set(payload['response']), {'threshold', 'pieces'})
        self.assertEqual(len(payload['response']['pieces']), 2)
        for piece in payload['response']['pieces']:
            self.assertEqual(set(piece), {'start', 'stop', 'slope', 'intercept', 'alarms'})
        self.assertEqual(payload['response']['pieces'][1]['start'], [10, 3])
        self.assertEqual(evaluate_response(restored.response, Fraction(13, 4)), TraceResult((), Fraction(47, 12)))
        self.assertEqual(evaluate_response(restored.response, Fraction(10, 3)), TraceResult((20,), Fraction(0)))
