import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from evidence.codec import encode_segment

if TYPE_CHECKING:
    from evidence.publish import SegmentStore


def write_delivery(destination: Path | str, payload: bytes) -> None:
    target = Path(destination)
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, prefix='.delivery-', delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_segment(store: 'SegmentStore', evidence_id: str, destination: Path | str) -> bytes:
    payload = encode_segment(store.get_published(evidence_id))
    write_delivery(destination, payload)
    return payload
