import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from plans.revisions import PlanRevision, RevisionLedger, check_identifier
from plans.thresholds import parse_threshold
from plans.units import parse_unit


@dataclass(frozen=True)
class RollAssignment:
    roll_id: str
    plan: PlanRevision

    def __post_init__(self):
        check_identifier(self.roll_id, 'roll ID')
        if not isinstance(self.plan, PlanRevision):
            raise ValueError('expected a fixed plan revision')


def initialize_plan_store(path: Path | str) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('BEGIN IMMEDIATE')
        RevisionLedger(db).initialize()
        db.execute('''
            CREATE TABLE IF NOT EXISTS roll_assignments (
                roll_id TEXT PRIMARY KEY NOT NULL,
                plan_id TEXT NOT NULL, revision TEXT NOT NULL,
                FOREIGN KEY (plan_id, revision) REFERENCES plan_revisions (plan_id, revision)
            )
        ''')


def _revision_key(db: sqlite3.Connection, roll_id: str) -> tuple[str, str] | None:
    return db.execute('''
        SELECT plan_id, revision FROM roll_assignments WHERE roll_id = ?
    ''', (roll_id,)).fetchone()


def register_plan(path: Path | str, roll_id: str, plan_id: str, revision: str,
                  unit: str, threshold: object) -> RollAssignment:
    plan = PlanRevision(plan_id, revision, parse_unit(unit), parse_threshold(threshold))
    assignment = RollAssignment(roll_id, plan)
    key = (plan_id, revision)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('BEGIN IMMEDIATE')
        RevisionLedger(db).save_revision(plan)
        current = _revision_key(db, roll_id)
        if current is None:
            db.execute('INSERT INTO roll_assignments VALUES (?, ?, ?)', (roll_id, *key))
        elif current != key:
            raise ValueError('roll already bound to a different plan revision')
    return assignment


def resolve_assignment(path: Path | str, roll_id: str) -> RollAssignment:
    check_identifier(roll_id, 'roll ID')
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN')
        key = _revision_key(db, roll_id)
        if key is None:
            raise KeyError(roll_id)
        return RollAssignment(roll_id, RevisionLedger(db).get_revision(*key))
