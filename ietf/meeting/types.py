# Copyright The IETF Trust 2023, All Rights Reserved
import strawberry
from strawberry import auto
from . import models

@strawberry.django.filters.filter(models.Meeting)
class MeetingFilter:
    number: auto
    city: auto

@strawberry.django.type(
    models.Meeting,
)
class Meeting:
    id: auto
    number: auto
    city: auto
