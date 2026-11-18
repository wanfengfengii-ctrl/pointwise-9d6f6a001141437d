import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from archive.receipts import IssueReceipt, check_receipt, make_receipt
from plans.revisions import revision_payload
from plans.thresholds import encode_rational
from reports.compose import ReportResult


@dataclass(frozen=True)
class IssuedReport:
    report_id: str
    result: ReportResult
    receipt: IssueReceipt

    def __post_init__(self):
        check_receipt(self.report_id, self.receipt)


def result_payload(result: ReportResult) -> dict:
    return {
        'roll_id': result.assignment.roll_id,
        'plan': revision_payload(result.assignment.plan),
        'coverage': [result.coverage.first, result.coverage.last],
        'references': [
            {'evidence_id': reference.evidence_id, 'digest': reference.digest}
            for reference in result.references
        ],
        'alarms': list(result.alarms),
        'amount': encode_rational(result.amount),
    }


class ArchiveStore:
    def __init__(self, path: Path | str):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA foreign_keys = ON')
            db.execute('BEGIN IMMEDIATE')
            db.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY NOT NULL, body TEXT NOT NULL
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL, report_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY (report_id) REFERENCES reports (report_id)
                )
            ''')

    def commit_issue(self, result: ReportResult) -> IssuedReport:
        report_id = uuid4().hex
        receipt = make_receipt(report_id)
        issued = IssuedReport(report_id, result, receipt)
        body = json.dumps(result_payload(result), sort_keys=True, separators=(',', ':'))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA foreign_keys = ON')
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO reports VALUES (?, ?)', (report_id, body))
            db.execute('INSERT INTO receipts VALUES (?, ?)', (receipt.receipt_id, receipt.report_id))
        return issued
