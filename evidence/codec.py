import json

from detector.intervals import RationalInterval
from detector.response import ResponsePiece, SegmentResponse
from evidence.binding import SegmentBinding, SegmentEvidence, validate_binding
from plans.revisions import revision_from_payload, revision_payload
from plans.thresholds import decode_rational, encode_rational
from recording.sequence import TickCoverage


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate evidence field {key}')
        result[key] = value
    return result


def _fields(value, names, label):
    if type(value) is not dict or value.keys() != names:
        raise ValueError(f'invalid {label} fields')
    return value


def _array(value, label):
    if type(value) is not list:
        raise ValueError(f'{label} must be an array')
    return value


def encode_segment(evidence: SegmentEvidence) -> bytes:
    validate_binding(evidence)
    binding = evidence.binding
    body = {
        'version': 1,
        'evidence_id': evidence.evidence_id,
        'binding': {
            'roll_id': binding.roll_id,
            'plan': revision_payload(binding.plan),
            'recording_id': binding.recording_id,
            'coverage': [binding.coverage.first, binding.coverage.last],
        },
        'response': {
            'threshold': encode_rational(evidence.response.threshold),
            'pieces': [
                {
                    'start': encode_rational(piece.interval.start),
                    'stop': encode_rational(piece.interval.stop),
                    'slope': piece.slope,
                    'intercept': encode_rational(piece.intercept),
                    'alarms': list(piece.alarms),
                }
                for piece in evidence.response.pieces
            ],
        },
    }
    return (json.dumps(body, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def _decode_piece(value) -> ResponsePiece:
    piece = _fields(value, {'start', 'stop', 'slope', 'intercept', 'alarms'}, 'response piece')
    interval = RationalInterval(decode_rational(piece['start']), decode_rational(piece['stop']))
    return ResponsePiece(interval, piece['slope'], decode_rational(piece['intercept']),
                         tuple(_array(piece['alarms'], 'piece alarms')))


def decode_segment(payload: bytes) -> SegmentEvidence:
    if type(payload) is not bytes:
        raise ValueError('segment payload must be bytes')
    body = _fields(json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_fields),
                   {'version', 'evidence_id', 'binding', 'response'}, 'segment')
    if type(body['version']) is not int or body['version'] != 1:
        raise ValueError('unsupported segment payload version')
    binding_data = _fields(body['binding'], {'roll_id', 'plan', 'recording_id', 'coverage'}, 'binding')
    bounds = _array(binding_data['coverage'], 'coverage')
    if len(bounds) != 2:
        raise ValueError('coverage requires two original ticks')
    binding = SegmentBinding(binding_data['roll_id'], revision_from_payload(binding_data['plan']),
                             binding_data['recording_id'], TickCoverage(*bounds))
    response_data = _fields(body['response'], {'threshold', 'pieces'}, 'response')
    response = SegmentResponse(decode_rational(response_data['threshold']), tuple(
        _decode_piece(piece) for piece in _array(response_data['pieces'], 'response pieces')
    ))
    evidence = SegmentEvidence(body['evidence_id'], binding, response)
    validate_binding(evidence)
    return evidence
