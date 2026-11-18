from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from detector.intervals import RationalInterval, check_partition
from detector.step import check_entry_amount
from detector.trace import TraceResult, evaluate_ticks
from plans.thresholds import parse_rational, parse_threshold
from recording.ingest import OriginalTick


@dataclass(frozen=True)
class ResponsePiece:
    interval: RationalInterval
    slope: int
    intercept: Fraction
    alarms: tuple[int, ...]

    def __post_init__(self):
        if type(self.slope) is not int or self.slope not in (0, 1):
            raise ValueError('response slope must equal zero or one')
        object.__setattr__(self, 'intercept', parse_rational(self.intercept))
        object.__setattr__(self, 'alarms', tuple(self.alarms))

    def exit_amount(self, entry: Fraction) -> Fraction:
        return self.slope * entry + self.intercept


@dataclass(frozen=True)
class SegmentResponse:
    threshold: Fraction
    pieces: tuple[ResponsePiece, ...]

    def __post_init__(self):
        object.__setattr__(self, 'threshold', parse_threshold(self.threshold))
        object.__setattr__(self, 'pieces', tuple(self.pieces))


def build_response(ticks: Iterable[OriginalTick], threshold: object) -> SegmentResponse:
    limit = parse_threshold(threshold)
    batch = tuple(ticks)
    if not batch:
        raise ValueError('response requires at least one tick')
    if any(right.number != left.number + 1 for left, right in zip(batch, batch[1:])):
        raise ValueError('response requires consecutive original ticks')
    trace = evaluate_ticks(batch, limit)
    piece = ResponsePiece(RationalInterval(0, limit), 0, trace.amount, trace.alarms)
    response = SegmentResponse(limit, (piece,))
    validate_response(response)
    return response


def validate_response(response: SegmentResponse) -> None:
    limit = response.threshold
    check_partition((piece.interval for piece in response.pieces), limit)
    for piece in response.pieces:
        low = piece.exit_amount(piece.interval.start)
        high_limit = piece.exit_amount(piece.interval.stop)
        if not 0 <= low < limit or high_limit > limit:
            raise ValueError('response exit amount lies outside [0, threshold)')
        if any(type(number) is not int for number in piece.alarms):
            raise ValueError('response alarms must be integer original ticks')
        if any(left >= right for left, right in zip(piece.alarms, piece.alarms[1:])):
            raise ValueError('response alarms must increase strictly')


def evaluate_response(response: SegmentResponse, entry: object) -> TraceResult:
    validate_response(response)
    amount = check_entry_amount(response.threshold, entry)
    for piece in response.pieces:
        if piece.interval.contains(amount):
            return TraceResult(piece.alarms, piece.exit_amount(amount))
    raise ValueError('response does not cover the requested entry amount')
