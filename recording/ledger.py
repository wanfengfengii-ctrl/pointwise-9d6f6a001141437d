import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from plans.assignments import RollAssignment
from plans.revisions import check_identifier, revision_from_payload, revision_payload
from plans.thresholds import decode_rational, encode_rational
from recording.ingest import OriginalTick
from recording.sequence import TickCoverage, check_contiguous


@dataclass(frozen=True)
class SealedRecording:
    recording_id: str
    assignment: RollAssignment
    coverage: TickCoverage
    ticks: tuple[OriginalTick, ...]

    def __post_init__(self):
        check_identifier(self.recording_id, 'recording ID')
        if not isinstance(self.assignment, RollAssignment):
            raise ValueError('expected a fixed roll assignment')
        object.__setattr__(self, 'ticks', check_contiguous(self.ticks, self.coverage))


class RecordingLedger:
    def __init__(self, path: Path | str):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS recordings (
                    recording_id TEXT PRIMARY KEY NOT NULL, body TEXT NOT NULL
                )
            ''')

    def save_sealed(self, recording: SealedRecording) -> SealedRecording:
        body = json.dumps({
            'roll_id': recording.assignment.roll_id,
            'plan': revision_payload(recording.assignment.plan),
            'coverage': [recording.coverage.first, recording.coverage.last],
            'ticks': [[tick.number, encode_rational(tick.deviation)] for tick in recording.ticks],
        }, sort_keys=True, separators=(',', ':'))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM recordings WHERE recording_id = ?',
                             (recording.recording_id,)).fetchone()
            if row is None:
                db.execute('INSERT INTO recordings VALUES (?, ?)', (recording.recording_id, body))
            elif row[0] != body:
                raise ValueError('conflicting sealed recording ID')
        return recording

    def get_sealed(self, recording_id: str) -> SealedRecording:
        check_identifier(recording_id, 'recording ID')
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT body FROM recordings WHERE recording_id = ?',
                             (recording_id,)).fetchone()
        if row is None:
            raise KeyError(recording_id)
        body = json.loads(row[0])
        return SealedRecording(
            recording_id,
            RollAssignment(body['roll_id'], revision_from_payload(body['plan'])),
            TickCoverage(*body['coverage']),
            tuple(OriginalTick(number, decode_rational(value)) for number, value in body['ticks']),
        )
