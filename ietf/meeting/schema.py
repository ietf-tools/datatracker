from typing_extensions import Required
import graphene
from graphene_django import DjangoObjectType

from .models import FloorPlan, Group, Meeting, MeetingTypeName, Room, Schedule, SchedTimeSessAssignment, Session, TimeSlot

class FloorPlanType(DjangoObjectType):
    class Meta:
        model = FloorPlan
        fields = "__all__"

class MeetingType(DjangoObjectType):
    class Meta:
        model = Meeting
        fields = "__all__"
        # exclude = ("meeting_set",)
        convert_choices_to_enum = False

class MeetingTypeNameType(DjangoObjectType):
    class Meta:
        model = MeetingTypeName
        # fields = "__all__"
        exclude = ("meeting_set",)

class RoomType(DjangoObjectType):
    class Meta:
        model = Room
        # fields = "__all__"
        exclude = ('meeting',)

class ScheduleType(DjangoObjectType):
    class Meta:
        model = Schedule
        fields = "__all__"

class SchedTimeSessAssignmentType(DjangoObjectType):
    class Meta:
        model = SchedTimeSessAssignment
        fields = "__all__"

class TimeSlotType(DjangoObjectType):
    class Meta:
        model = TimeSlot
        # fields = "__all__"
        exclude = ("sessionassignments",)

class SessionType(DjangoObjectType):
    class Meta:
        model = Session
        fields = "__all__"

class GroupType(DjangoObjectType):
    class Meta:
        model = Group
        fields = "__all__"

class Query(graphene.ObjectType):
    meeting_by_id = graphene.Field(MeetingType, id=graphene.Int(required=True))
    meeting_by_number = graphene.Field(MeetingType, number=graphene.Int(required=True))
    meeting_current = graphene.Field(MeetingType)
    # meetings = graphene.List(MeetingType)

    def resolve_meeting_by_id(root, info, id):
        return Meeting.objects.get(pk=id)

    def resolve_meeting_by_number(root, info, number):
        return Meeting.objects.get(number=number)

    def resolve_meeting_current(root, info):
        return Meeting.get_current_meeting()

    # def resolve_meetings(root, info):
    #     return Meeting.objects.all()
