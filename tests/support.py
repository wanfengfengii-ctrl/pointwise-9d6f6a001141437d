import json
import shutil
import sqlite3
import unittest
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.commit import ArchiveStore
from evidence.export import export_segment
from evidence.publish import SegmentStore, publish_segment
from plans.assignments import initialize_plan_store, register_plan
from recording.ledger import RecordingLedger
from recording.segments import seal_recording
from recording.sequence import TickCoverage


def rows_for(assignment, pairs):
    return [
        {
            'roll_id': assignment.roll_id, 'plan_id': assignment.plan.plan_id,
            'revision': assignment.plan.revision, 'unit': assignment.plan.unit.value,
            'tick': number, 'deviation': value,
        }
        for number, value in pairs
    ]


def record_count(path, table):
    if table not in {'plan_revisions', 'roll_assignments', 'recordings', 'published_segments', 'reports', 'receipts'}:
        raise ValueError(table)
    with closing(sqlite3.connect(path)) as db:
        return db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]


class Station:
    def __init__(self, root, roll_id, revision, threshold):
        root.mkdir()
        self.root = root
        self.path = root / 'station.sqlite'
        self.recordings = RecordingLedger(self.path)
        self.segments = SegmentStore(self.path)
        self.initialize()
        self.assignment = register_plan(self.path, roll_id, 'surface', revision, 'du', threshold)

    def initialize(self):
        initialize_plan_store(self.path)
        self.recordings.initialize()
        self.segments.initialize()

    def seal(self, recording_id, first, deviations):
        coverage = TickCoverage(first, first + len(deviations) - 1)
        return seal_recording(self.recordings, recording_id, self.assignment.roll_id, coverage,
                              rows_for(self.assignment, enumerate(deviations, first)))

    def publish(self, recording_id, evidence_id, first, last):
        return publish_segment(self.recordings, self.segments, recording_id, evidence_id,
                               TickCoverage(first, last))

    def detach(self):
        shutil.rmtree(self.root)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.transfer = self.root / 'transfer'
        self.transfer.mkdir()
        self.station = self.new_station('station')
        quality = self.root / 'quality'
        quality.mkdir()
        self.archive = ArchiveStore(quality / 'archive.sqlite')
        self.archive.initialize()

    def new_station(self, name, roll_id='roll-A', revision='r1', threshold=5):
        return Station(self.root / name, roll_id, revision, threshold)

    def handoff(self, station, recording_id, evidence_id, first, last):
        station.publish(recording_id, evidence_id, first, last)
        target = self.transfer / f'{evidence_id}.json'
        export_segment(station.segments, evidence_id, target)
        return target

    def archive_counts(self):
        return (record_count(self.archive.path, 'reports'), record_count(self.archive.path, 'receipts'))


def independent_recurrence(first, deviations, threshold):
    amount = Fraction(0)
    alarms = []
    for number, deviation in enumerate(deviations, first):
        amount += deviation
        if amount >= threshold:
            alarms.append(number)
            amount = Fraction(0)
        elif amount < 0:
            amount = Fraction(0)
    return tuple(alarms), amount


def supplied_handoffs():
    """Fixed payloads calculated from the arithmetic of the two short shifts."""
    white_pieces = (
        {'start': [0, 1], 'stop': [1, 1], 'slope': 1, 'intercept': [4, 1], 'alarms': []},
        {'start': [1, 1], 'stop': [5, 1], 'slope': 0, 'intercept': [0, 1], 'alarms': [1]},
    )
    night_pieces = (
        {'start': [0, 1], 'stop': [3, 1], 'slope': 1, 'intercept': [1, 1], 'alarms': []},
        {'start': [3, 1], 'stop': [5, 1], 'slope': 0, 'intercept': [0, 1], 'alarms': [2]},
    )
    payloads = []
    for name, bounds, pieces in (('white', [1, 1], white_pieces), ('night', [2, 3], night_pieces)):
        payloads.append(json.dumps({
            'version': 1,
            'evidence_id': f'provided-{name}',
            'binding': {
                'roll_id': 'roll-A', 'recording_id': f'offline-{name}', 'coverage': bounds,
                'plan': {'plan_id': 'surface', 'revision': 'r1', 'unit': 'du', 'threshold': [5, 1]},
            },
            'response': {'threshold': [5, 1], 'pieces': pieces},
        }).encode('ascii'))
    return tuple(payloads)
