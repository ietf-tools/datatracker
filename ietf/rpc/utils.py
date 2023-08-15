from typing import List

from ietf.doc.models import Document
from .models import RfcToBe, UnusableRfcNumber


def next_rfc_number(count=1) -> List[int]:
    """Find the next count contiguous available RFC numbers"""
    # todo implement me
