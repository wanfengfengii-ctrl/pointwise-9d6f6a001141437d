"""Regressions for the CW-17 cross-shift alarm miss.

The defect collapsed each sealed shift into a single slope-zero response, so an
alarm that depended on the incoming amount was dropped, and issuing restarted
every shift from zero.  These checks pin the intended arithmetic down:
piecewise responses must answer any exact entry amount in ``[0, H)`` with the
original-tick alarms, and a whole roll must chain segment exits from zero.
"""
from fractions import Fraction
from random import Random

from archive.commit import ArchiveStore
from archive.read import read_report
from detector.response import build_response, evaluate_response
from detector.trace import TraceResult
from evidence.codec import decode_segment, encode_segment
from recording.ingest import OriginalTick
from recording.sequence import TickCoverage
from reports.issue import issue_report
from tests.support import ProjectCase, independent_recurrence, supplied_handoffs


ENTRIES = (Fraction(0), Fraction(1, 3), Fraction(5, 2), Fraction(3), Fraction(10, 3),
           Fraction(4), Fraction(9, 2), Fraction(25, 6), Fraction(29, 6), Fraction(103, 24))


def sweep(response):
    for entry in ENTRIES:
        yield entry, evaluate_response(response, entry)


class CrossShiftTests(ProjectCase):
    def test_incident_night_segment(self):
        self.station.seal('early', 2, (2, -1))
        response = self.station.publish('early', 'early', 2, 3).response
        expected = {
            Fraction(0): ((), Fraction(1)),
            Fraction(3): ((2,), Fraction(0)),
            Fraction(4): ((2,), Fraction(0)),
        }
        for entry, wanted in expected.items():
            trace = evaluate_response(response, entry)
            self.assertEqual((trace.alarms, trace.amount), wanted, msg=f'entry={entry}')
        for entry, trace in sweep(response):
            if entry == 4:
                self.assertEqual((trace.alarms, trace.amount), ((2,), Fraction(0)))

    def test_night_control_differs_only_by_entry(self):
        self.station.seal('early', 2, (2, -1))
        self.station.seal('late', 2, (0, 1))
        early = self.station.publish('early', 'early', 2, 3).response
        late = self.station.publish('late', 'late', 2, 3).response
        self.assertEqual(evaluate_response(early, 0), TraceResult((), Fraction(1)))
        self.assertEqual(evaluate_response(late, 0), TraceResult((), Fraction(1)))
        self.assertEqual(evaluate_response(early, 4), TraceResult((2,), Fraction(0)))
        self.assertEqual(evaluate_response(late, 4), TraceResult((3,), Fraction(0)))
        self.assertEqual(evaluate_response(early, 3), TraceResult((2,), Fraction(0)))

    def test_whole_roll_matches_recurrence(self):
        scenarios = (
            (1, (4, 2, -1), ((1, 3),)),
            (1, (4, 2, -1), ((1, 1), (2, 3))),
            (1, (4, 2, -1), ((1, 1), (2, 2), (3, 3))),
            (11, (-3, Fraction(1, 2), Fraction(9, 2), 6, -1, Fraction(13, 4)),
             ((11, 12), (13, 16))),
            (11, (-3, Fraction(1, 2), Fraction(9, 2), 6, -1, Fraction(13, 4)),
             ((11, 12), (13, 13), (14, 16))),
        )
        for case, (first, deviations, partition) in enumerate(scenarios):
            with self.subTest(deviations=deviations, partition=partition):
                station = self.new_station(f'scenario-{case}')
                for index, (left, right) in enumerate(partition):
                    offset = left - first
                    station.seal(f'shift-{index}', left,
                                 deviations[offset:offset + right - left + 1])
                paths = [self.handoff(station, f'shift-{index}', f'part-{index}', left, right)
                         for index, (left, right) in enumerate(partition)]
                coverage = TickCoverage(first, first + len(deviations) - 1)
                expected = independent_recurrence(first, deviations, 5)
                for reversal in (False, True):
                    supplied = tuple(path.read_bytes()
                                     for path in (reversed(paths) if reversal else paths))
                    issued = issue_report(self.archive, station.assignment, coverage, supplied)
                    self.assertEqual((issued.result.alarms, issued.result.amount), expected)
                    self.assertEqual(read_report(self.archive, issued.report_id).report, issued)
                    self.assertEqual(
                        tuple(ref.evidence_id for ref in issued.result.references),
                        tuple(path.stem for path in paths))

    def test_response_matches_recurrence_for_random_entries(self):
        random = Random(17)
        for case in range(60):
            deviations = tuple(Fraction(random.randint(-6, 9), random.choice((1, 2, 3)))
                               for _ in range(random.randint(1, 6)))
            first = random.randint(0, 20)
            ticks = [OriginalTick(number, deviation)
                     for number, deviation in enumerate(deviations, first)]
            response = build_response(ticks, 5)
            for entry in ENTRIES:
                trace = evaluate_response(response, entry)
                expected = independent_recurrence(first, deviations, 5, entry=entry)
                self.assertEqual((trace.alarms, trace.amount), expected,
                                 msg=f'case={case} entry={entry} deviations={deviations}')

    def test_offline_supplied_round_trip(self):
        assignment = self.station.assignment
        self.station.detach()
        white, night = supplied_handoffs()
        for payload in (white, night):
            self.assertEqual(decode_segment(encode_segment(decode_segment(payload))), decode_segment(payload))
        issued = issue_report(self.archive, assignment, TickCoverage(1, 3), (night, white))
        self.assertEqual((issued.result.alarms, issued.result.amount), ((2,), Fraction(0)))
        self.assertEqual(tuple(ref.evidence_id for ref in issued.result.references),
                         ('provided-white', 'provided-night'))
        reopened = ArchiveStore(self.archive.path)
        reopened.initialize()
        self.assertEqual(read_report(reopened, issued.report_id).report, issued)
        self.assertEqual(self.archive_counts(), (1, 1))
