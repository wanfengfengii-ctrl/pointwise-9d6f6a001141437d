import argparse
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.commit import ArchiveStore
from archive.export import export_report
from archive.read import read_report
from detector.trace import preview
from evidence.export import export_segment
from evidence.publish import SegmentStore, publish_segment
from plans.assignments import initialize_plan_store, register_plan
from plans.thresholds import encode_rational
from recording.ledger import RecordingLedger
from recording.segments import seal_recording
from recording.sequence import TickCoverage
from reports.issue import issue_report


def result_values(result):
    return {'alarms': list(result.alarms), 'amount': encode_rational(result.amount)}


def run_demo(scenario):
    with TemporaryDirectory(prefix='surface-inspection-') as directory:
        root = Path(directory)
        station = root / 'station'
        transfer = root / 'transfer'
        quality = root / 'quality'
        for working_directory in (station, transfer, quality):
            working_directory.mkdir()
        path = station / 'station.sqlite'
        initialize_plan_store(path)
        recordings = RecordingLedger(path)
        recordings.initialize()
        segments = SegmentStore(path)
        segments.initialize()
        identity = {key: scenario[key] for key in ('roll_id', 'plan_id', 'revision', 'unit')}
        assignment = register_plan(path, **identity, threshold=scenario['threshold'])
        handoffs = []
        previews = {}
        for shift in scenario['shifts']:
            coverage = TickCoverage(*shift['coverage'])
            rows = [dict(identity, tick=number, deviation=value) for number, value in shift['ticks']]
            recording_id = shift['recording_id']
            evidence_id = shift['evidence_id']
            seal_recording(recordings, recording_id, assignment.roll_id, coverage, rows)
            previews[recording_id] = result_values(preview(recordings, recording_id))
            publish_segment(recordings, segments, recording_id, evidence_id, coverage)
            output = transfer / f'segment-{len(handoffs)}.json'
            export_segment(segments, evidence_id, output)
            handoffs.append(output)

        shutil.rmtree(station)
        archive = ArchiveStore(quality / 'archive.sqlite')
        archive.initialize()
        issued = issue_report(archive, assignment, TickCoverage(*scenario['coverage']),
                              (output.read_bytes() for output in reversed(handoffs)))
        actual = result_values(issued.result)
        expected = {'alarms': [2], 'amount': [0, 1]}
        lookup = read_report(ArchiveStore(archive.path), issued.report_id)
        if lookup.report != issued or actual != expected:
            raise RuntimeError(f'demo report differs from the worked sample: {actual!r}')
        expected_previews = {'white': {'alarms': [], 'amount': [4, 1]},
                             'night': {'alarms': [], 'amount': [1, 1]}}
        if previews != expected_previews:
            raise RuntimeError(f'demo station previews differ from the worked sample: {previews!r}')
        destination = transfer / 'inspection-report.json'
        delivery = export_report(archive, issued.report_id, destination)
        delivered = json.loads(destination.read_bytes())
        expected_delivery = {
            'report_id': issued.report_id,
            'receipt_id': issued.receipt.receipt_id,
            'evidence_ids': ['CW-17-white', 'CW-17-night'],
            **expected,
        }
        delivered_result = delivered['result']
        actual_delivery = {
            'report_id': delivered['report_id'], 'receipt_id': delivered['receipt']['receipt_id'],
            'evidence_ids': [reference['evidence_id'] for reference in delivered_result['references']],
            'alarms': delivered_result['alarms'], 'amount': delivered_result['amount'],
        }
        if (delivery.payload != destination.read_bytes() or actual_delivery != expected_delivery
                or delivered['receipt']['report_id'] != issued.report_id):
            raise RuntimeError(f'demo delivery differs from the issued report: {actual_delivery!r}')
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'compose', 'input': scenario, 'expected': expected, 'actual': actual,
            'downstream_expected': expected_delivery, 'downstream_actual': actual_delivery,
            'code_paths': ['recording/segments.py', 'evidence/publish.py', 'reports/issue.py',
                           'reports/compose.py', 'archive/export.py'],
            'oracle': 'Manual recurrence: amount 4 at tick 1, 6 at tick 2 alarms and resets, -1 at tick 3 floors to 0.',
        }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description='Run the CW-17 surface inspection example')
    parser.add_argument('sample', type=Path, choices=(Path('sample/roll.json'),))
    args = parser.parse_args()
    run_demo(json.loads(args.sample.read_text(encoding='utf-8')))


if __name__ == '__main__':
    main()
