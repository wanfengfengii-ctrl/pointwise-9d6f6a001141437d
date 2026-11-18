import json
from dataclasses import dataclass
from pathlib import Path

from archive.commit import ArchiveStore, result_payload
from archive.read import read_report
from evidence.export import write_delivery


@dataclass(frozen=True)
class ReportDelivery:
    report_id: str
    payload: bytes


def export_report(archive: ArchiveStore, report_id: str, destination: Path | str) -> ReportDelivery:
    report = read_report(archive, report_id).report
    if report is None:
        raise KeyError(report_id)
    body = {
        'version': 1,
        'report_id': report.report_id,
        'result': result_payload(report.result),
        'receipt': {'receipt_id': report.receipt.receipt_id, 'report_id': report.receipt.report_id},
    }
    payload = (json.dumps(body, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    write_delivery(destination, payload)
    return ReportDelivery(report.report_id, payload)
