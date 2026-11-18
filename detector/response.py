from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from detector.intervals import RationalInterval, check_partition
from detector.step import check_entry_amount
from detector.trace import TraceResult
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


def _advance_piece(piece: ResponsePiece, limit: Fraction, number: int,
                   deviation: Fraction) -> tuple[ResponsePiece, ...]:
    """Propagate one original tick through a piece, keeping exact boundaries.

    The exit value as a function of the entry is ``slope * entry + intercept``.
    After adding the signed deviation, negative values are floored to zero and
    values that reach the threshold alarm on this original tick and reset to
    zero.  Crossing points stay exact rationals, so no arbitrary partitioning is
    introduced by the detector.
    """
    interval = piece.interval
    if piece.slope == 0:
        value = piece.intercept + deviation
        if value >= limit:
            return (ResponsePiece(interval, 0, Fraction(0), piece.alarms + (number,)),)
        if value < 0:
            return (ResponsePiece(interval, 0, Fraction(0), piece.alarms),)
        return (ResponsePiece(interval, 0, value, piece.alarms),)
    offset = piece.intercept + deviation
    crossings = sorted(
        point for point in (Fraction(0) - offset, limit - offset)
        if interval.start < point < interval.stop
    )
    bounds = [interval.start, *crossings, interval.stop]
    advanced = []
    for left, right in zip(bounds, bounds[1:]):
        middle = (left + right) / 2
        value = middle + offset
        if value >= limit:
            advanced.append(ResponsePiece(RationalInterval(left, right), 0, Fraction(0),
                                          piece.alarms + (number,)))
        elif value < 0:
            advanced.append(ResponsePiece(RationalInterval(left, right), 0, Fraction(0),
                                          piece.alarms))
        else:
            advanced.append(ResponsePiece(RationalInterval(left, right), 1, offset, piece.alarms))
    return tuple(advanced)


def _merge_pieces(pieces: Iterable[ResponsePiece]) -> tuple[ResponsePiece, ...]:
    merged: list[ResponsePiece] = []
    for piece in pieces:
        if merged:
            last = merged[-1]
            if (last.interval.stop == piece.interval.start and last.slope == piece.slope
                    and last.intercept == piece.intercept and last.alarms == piece.alarms):
                merged[-1] = ResponsePiece(
                    RationalInterval(last.interval.start, piece.interval.stop),
                    piece.slope, piece.intercept, piece.alarms,
                )
                continue
        merged.append(piece)
    return tuple(merged)


def build_response(ticks: Iterable[OriginalTick], threshold: object) -> SegmentResponse:
    limit = parse_threshold(threshold)
    batch = tuple(ticks)
    if not batch:
        raise ValueError('response requires at least one tick')
    if any(right.number != left.number + 1 for left, right in zip(batch, batch[1:])):
        raise ValueError('response requires consecutive original ticks')
    pieces: tuple[ResponsePiece, ...] = (
        ResponsePiece(RationalInterval(0, limit), 1, Fraction(0), ()),
    )
    for tick in batch:
        advanced = []
        for piece in pieces:
            advanced.extend(_advance_piece(piece, limit, tick.number, tick.deviation))
        pieces = _merge_pieces(advanced)
    response = SegmentResponse(limit, pieces)
    validate_response(response)
    return response


def validate_response(response: SegmentResponse) -> None:
    limit = response.threshold
    if not response.pieces:
        raise ValueError('response requires at least one piece')
    check_partition((piece.interval for piece in response.pieces), limit)
    for piece in response.pieces:
        low = piece.exit_amount(piece.interval.start)
        high_limit = piece.exit_amount(piece.interval.stop)
        if piece.slope == 1:
            # The exit value approaches both ends from inside the half-open interval.
            if not 0 <= low < limit or high_limit > limit:
                raise ValueError('response exit amount lies outside [0, threshold)')
        elif not 0 <= low < limit:
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
