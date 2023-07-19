# Copyright The IETF Trust 2023, All Rights Reserved
from typing import TYPE_CHECKING, Annotated

import strawberry
from strawberry import auto

from . import models

if TYPE_CHECKING:
    from ietf.name.types import MeetingTypeName

@strawberry.django.filters.filter(models.Meeting)
class MeetingFilter:
    number: auto
    city: auto
    type: auto

@strawberry.django.type(
    models.Meeting,
)
class Meeting:
    id: auto
    number: auto
    city: auto
    type: Annotated["MeetingTypeName", strawberry.lazy("ietf.name.types")]
