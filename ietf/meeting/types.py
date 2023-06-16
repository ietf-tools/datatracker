import strawberry
from strawberry import auto
from typing import List
from . import models

@strawberry.django.filters.filter(models.Meeting)
class MeetingFilter:
    number: auto
    city: auto

@strawberry.django.type(
    models.Meeting,
    description='Meeting Object'
)
class Meeting:
    id: auto
    number: auto
    city: auto
