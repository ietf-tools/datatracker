# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-
from typing import List

from django.db.models import Max, PositiveIntegerField
from django.db.models.functions import Cast, Substr

from ietf.doc.models import DocAlias
from .models import RfcToBe, UnusableRfcNumber


def next_rfc_number(count=1) -> List[int]:
    """Find the next count contiguous available RFC numbers"""
    # In the worst-case, we can always use (n + 1) to (n + count) where n is the last
    # unavailable number.
    last_unavailable_number = max((
        UnusableRfcNumber.objects.aggregate(Max("number"))["number__max"] or 0,
        RfcToBe.objects.aggregate(Max("rfc_number"))["rfc_number__max"] or 0,
        DocAlias.objects.filter(name__startswith="rfc").annotate(
            rfcnum=Cast(Substr("name", 4), PositiveIntegerField())
        ).aggregate(Max("rfcnum"))["rfcnum__max"],
    ))
    # todo consider holes in the unavailable number sequence!
    return list(range(last_unavailable_number + 1, last_unavailable_number + 1 + count))
