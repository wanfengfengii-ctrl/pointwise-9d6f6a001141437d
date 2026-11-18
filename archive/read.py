import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from archive.commit import ArchiveStore, IssuedReport
from archive.receipts import IssueReceipt
from plans.assignments import RollAssignment
from plans.revisions import check_identifier, revision_from_payload
from plans.thresholds import decode_rational
from recording.sequence import TickCoverage
from reports.accept import SegmentReference
from reports.compose import ReportResult


@dataclass(frozen=True)
class ReportLookup:
    requested_id: str
    report: IssuedReport | None

    @property
    def found(self) -> bool:
        return self.report is not None


def _decode_result(body: str) -> ReportResult:
    payload = json.loads(body)
    return ReportResult(
        RollAssignment(payload['roll_id'], revision_from_payload(payload['plan'])),
        TickCoverage(*payload['coverage']),
        tuple(SegmentReference(**reference) for reference in payload['references']),
        tuple(payload['alarms']),
        decode_rational(payload['amount']),
    )


def read_report(archive: ArchiveStore, report_id: str) -> ReportLookup:
    check_identifier(report_id, 'report ID')
    with closing(sqlite3.connect(archive.path)) as db:
        row = db.execute('''
            SELECT reports.body, receipts.receipt_id, receipts.report_id
            FROM reports LEFT JOIN receipts ON receipts.report_id = reports.report_id
            WHERE reports.report_id = ?
        ''', (report_id,)).fetchone()
    if row is None:
        return ReportLookup(report_id, None)
    body, receipt_id, receipt_report_id = row
    if receipt_id is None:
        raise ValueError('archived report has no matching receipt')
    receipt = IssueReceipt(receipt_id, receipt_report_id)
    return ReportLookup(report_id, IssuedReport(report_id, _decode_result(body), receipt))
