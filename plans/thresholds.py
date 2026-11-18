import re
from fractions import Fraction


_RATIONAL_TEXT = re.compile(r'[+-]?[0-9]+(?:/[0-9]+|\.[0-9]+)?')


def parse_rational(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str) and _RATIONAL_TEXT.fullmatch(value):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid rational text') from exc
    if isinstance(value, (list, tuple)) and len(value) == 2:
        numerator, denominator = value
        if type(numerator) is int and type(denominator) is int and denominator > 0:
            return Fraction(numerator, denominator)
    raise ValueError('expected an exact rational with a positive denominator')


def encode_rational(value: object) -> list[int]:
    amount = parse_rational(value)
    return [amount.numerator, amount.denominator]


def decode_rational(value: object) -> Fraction:
    if type(value) is not list:
        raise ValueError('expected a rational pair in the payload')
    amount = parse_rational(value)
    if value != encode_rational(amount):
        raise ValueError('noncanonical rational pair')
    return amount


def parse_threshold(value: object) -> Fraction:
    threshold = parse_rational(value)
    if threshold <= 0:
        raise ValueError('threshold must be strictly positive')
    return threshold
