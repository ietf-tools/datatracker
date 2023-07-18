# Copyright The IETF Trust 2023, All Rights Reserved

from typing import List
import strawberry

from ietf.meeting.types import Meeting, MeetingFilter

@strawberry.type
class Query:
    meetingById: Meeting = strawberry.django.field()
    meetings: List[Meeting] = strawberry.django.field(pagination=True, filters=MeetingFilter)

schema = strawberry.Schema(
    Query
)
