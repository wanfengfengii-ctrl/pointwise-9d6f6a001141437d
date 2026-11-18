import json
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.commit import ArchiveStore
from archive.read import read_report
from detector.response import evaluate_response
from evidence.codec import decode_segment
from evidence.export import export_segment
from recording.sequence import TickCoverage
from reports.issue import issue_report
from tests.support import Station, supplied_handoffs


EXPECTED = {
    "early-entry-0": {"alarms": [], "amount": "1"},
    "late-entry-0": {"alarms": [], "amount": "1"},
    "early-entry-3": {"alarms": [2], "amount": "0"},
    "early-entry-4": {"alarms": [2], "amount": "0"},
    "late-entry-4": {"alarms": [3], "amount": "0"},
    "offline-supplied": {"alarms": [2], "amount": "0"},
    "offline-early": {"alarms": [2], "amount": "0"},
    "offline-late": {"alarms": [3], "amount": "0"},
}


def observe(result):
    return {"alarms": list(result.alarms), "amount": str(result.amount)}


def collect(root):
    station = Station(root / "station", "roll-A", "r1", 5)
    transfer = root / "transfer"
    transfer.mkdir()
    payloads = {}
    for name, first, deviations in (("white", 1, (4,)), ("early", 2, (2, -1)), ("late", 2, (0, 1))):
        station.seal(name, first, deviations)
        station.publish(name, name, first, first + len(deviations) - 1)
        target = transfer / f"{name}.json"
        export_segment(station.segments, name, target)
        payloads[name] = target.read_bytes()
    assignment = station.assignment
    station.detach()
    archive = ArchiveStore(root / "archive.sqlite")
    archive.initialize()
    actual = {}
    for name, entry in (("early", 0), ("late", 0), ("early", 3), ("early", 4), ("late", 4)):
        evidence = decode_segment(payloads[name])
        actual[f"{name}-entry-{entry}"] = observe(evaluate_response(evidence.response, entry))
    white, night = supplied_handoffs()
    for name, inputs in (
        ("offline-supplied", (night, white)),
        ("offline-early", (payloads["early"], payloads["white"])),
        ("offline-late", (payloads["late"], payloads["white"])),
    ):
        issued = issue_report(archive, assignment, TickCoverage(1, 3), inputs)
        if read_report(ArchiveStore(archive.path), issued.report_id).report != issued:
            raise RuntimeError("issued report and receipt did not read back together")
        actual[name] = observe(issued.result)
    return actual


def main():
    with TemporaryDirectory(prefix="cross-shift-") as directory:
        actual = collect(Path(directory))
    mismatches = []
    for case, expected in EXPECTED.items():
        observed = actual[case]
        print(json.dumps({"case": case, "actual": observed, "expected": expected}, sort_keys=True))
        if observed != expected:
            mismatches.append(case)
    if mismatches:
        print("CROSS_SHIFT_ALARM_MISSING " + ", ".join(mismatches))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
