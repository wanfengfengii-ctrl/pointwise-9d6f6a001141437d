import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from plans.thresholds import decode_rational, encode_rational, parse_threshold
from plans.units import DeviationUnit, parse_unit


def check_identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f'{field} must be nonempty text without surrounding whitespace')
    if not value.isprintable():
        raise ValueError(f'{field} must use printable text')
    return value


@dataclass(frozen=True)
class PlanRevision:
    plan_id: str
    revision: str
    unit: DeviationUnit
    threshold: Fraction

    def __post_init__(self):
        check_identifier(self.plan_id, 'plan ID')
        check_identifier(self.revision, 'revision')
        object.__setattr__(self, 'unit', parse_unit(self.unit))
        object.__setattr__(self, 'threshold', parse_threshold(self.threshold))


def revision_payload(plan: PlanRevision) -> dict:
    return {
        'plan_id': plan.plan_id,
        'revision': plan.revision,
        'unit': plan.unit.value,
        'threshold': encode_rational(plan.threshold),
    }


def revision_from_payload(payload: object) -> PlanRevision:
    if not isinstance(payload, dict) or payload.keys() != {'plan_id', 'revision', 'unit', 'threshold'}:
        raise ValueError('invalid plan payload')
    return PlanRevision(
        payload['plan_id'], payload['revision'], payload['unit'],
        decode_rational(payload['threshold']),
    )


class RevisionLedger:
    """Use the caller's SQLite transaction for plan and binding changes."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS plan_revisions (
                plan_id TEXT NOT NULL, revision TEXT NOT NULL, unit TEXT NOT NULL,
                numerator TEXT NOT NULL, denominator TEXT NOT NULL,
                PRIMARY KEY (plan_id, revision)
            )
        ''')

    def get_revision(self, plan_id: str, revision: str) -> PlanRevision:
        row = self.db.execute('''
            SELECT unit, numerator, denominator FROM plan_revisions
            WHERE plan_id = ? AND revision = ?
        ''', (plan_id, revision)).fetchone()
        if row is None:
            raise KeyError((plan_id, revision))
        unit, numerator, denominator = row
        return PlanRevision(plan_id, revision, unit, Fraction(int(numerator), int(denominator)))

    def save_revision(self, plan: PlanRevision) -> PlanRevision:
        try:
            existing = self.get_revision(plan.plan_id, plan.revision)
        except KeyError:
            numerator, denominator = encode_rational(plan.threshold)
            self.db.execute('''
                INSERT INTO plan_revisions (plan_id, revision, unit, numerator, denominator)
                VALUES (?, ?, ?, ?, ?)
            ''', (plan.plan_id, plan.revision, plan.unit.value, str(numerator), str(denominator)))
            return plan
        if existing != plan:
            raise ValueError('conflicting fixed plan revision')
        return existing
