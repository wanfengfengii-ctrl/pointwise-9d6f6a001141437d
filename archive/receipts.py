from dataclasses import dataclass
from uuid import uuid4

from plans.revisions import check_identifier


@dataclass(frozen=True)
class IssueReceipt:
    receipt_id: str
    report_id: str


def make_receipt(report_id: str) -> IssueReceipt:
    check_identifier(report_id, 'report ID')
    return IssueReceipt(uuid4().hex, report_id)


def check_receipt(report_id: str, receipt: IssueReceipt) -> None:
    check_identifier(report_id, 'report ID')
    check_identifier(receipt.receipt_id, 'receipt ID')
    if receipt.report_id != report_id:
        raise ValueError('receipt is linked to a different report')
