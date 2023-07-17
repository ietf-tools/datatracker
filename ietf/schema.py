from typing import List
import strawberry
from strawberry_django_plus.optimizer import DjangoOptimizerExtension

from ietf.meeting.types import Meeting, MeetingFilter

@strawberry.type
class Query:
    meetingById: Meeting = strawberry.django.field()
    meetings: List[Meeting] = strawberry.django.field(pagination=True, filters=MeetingFilter)

schema = strawberry.Schema(
    Query,
    extensions=[
        DjangoOptimizerExtension
    ]
)
