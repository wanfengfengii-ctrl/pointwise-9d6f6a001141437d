import sqlite3
from contextlib import closing
from pathlib import Path

from detector.response import build_response
from evidence.binding import SegmentEvidence, make_binding
from evidence.codec import decode_segment, encode_segment
from plans.revisions import check_identifier
from recording.ledger import RecordingLedger
from recording.segments import select_ticks
from recording.sequence import TickCoverage


class SegmentStore:
    def __init__(self, path: Path | str):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS published_segments (
                    evidence_id TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL
                )
            ''')

    def save_published(self, evidence: SegmentEvidence) -> SegmentEvidence:
        payload = encode_segment(evidence)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM published_segments WHERE evidence_id = ?',
                             (evidence.evidence_id,)).fetchone()
            if row is None:
                db.execute('INSERT INTO published_segments VALUES (?, ?)', (evidence.evidence_id, payload))
            elif row[0] != payload:
                raise ValueError('conflicting fixed evidence ID')
        return evidence

    def get_published(self, evidence_id: str) -> SegmentEvidence:
        check_identifier(evidence_id, 'evidence ID')
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT payload FROM published_segments WHERE evidence_id = ?',
                             (evidence_id,)).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        evidence = decode_segment(row[0])
        if evidence.evidence_id != evidence_id:
            raise ValueError('fixed evidence ID differs from its store key')
        return evidence


def publish_segment(recordings: RecordingLedger, store: SegmentStore, recording_id: str,
                    evidence_id: str, coverage: TickCoverage) -> SegmentEvidence:
    check_identifier(evidence_id, 'evidence ID')
    recording = recordings.get_sealed(recording_id)
    ticks = select_ticks(recording, coverage)
    binding = make_binding(recording, coverage)
    response = build_response(ticks, recording.assignment.plan.threshold)
    return store.save_published(SegmentEvidence(evidence_id, binding, response))
