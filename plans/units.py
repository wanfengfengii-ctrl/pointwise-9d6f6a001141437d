from enum import StrEnum


class DeviationUnit(StrEnum):
    DETECTOR_UNIT = 'du'


SUPPORTED_UNITS = frozenset(unit.value for unit in DeviationUnit)


def parse_unit(value: object) -> DeviationUnit:
    if not isinstance(value, str) or value not in SUPPORTED_UNITS:
        raise ValueError('unsupported deviation unit')
    return DeviationUnit(value)
