# Copyright The IETF Trust 2023, All Rights Reserved
import strawberry
from strawberry import auto
from strawberry.scalars import JSON

from . import models

@strawberry.django.type(models.GroupStateName, fields="__all__")
class GroupStateName:
    pass

@strawberry.django.type(models.GroupTypeName, fields="__all__")
class GroupTypeName:
    pass

@strawberry.django.type(models.GroupMilestoneStateName, fields="__all__")
class GroupMilestoneStateName:
    pass

@strawberry.django.type(models.RoleName, fields="__all__")
class RoleName:
    pass

@strawberry.django.type(models.StreamName, fields="__all__")
class StreamName:
    pass

@strawberry.django.type(models.DocRelationshipName, fields="__all__")
class DocRelationshipName:
    pass

@strawberry.django.type(models.DocTypeName, fields="__all__")
class DocTypeName:
    pass

@strawberry.django.type(models.DocTagName, fields="__all__")
class DocTagName:
    pass

@strawberry.django.type(models.StdLevelName, fields="__all__")
class StdLevelName:
    pass

@strawberry.django.type(models.IntendedStdLevelName, fields="__all__")
class IntendedStdLevelName:
    pass

@strawberry.django.type(models.FormalLanguageName, fields="__all__")
class FormalLanguageName:
    pass

@strawberry.django.type(models.DocReminderTypeName, fields="__all__")
class DocReminderTypeName:
    pass

@strawberry.django.type(models.BallotPositionName, fields="__all__")
class BallotPositionName:
    pass

@strawberry.django.type(models.MeetingTypeName, fields="__all__")
class MeetingTypeName:
    pass

@strawberry.django.type(models.ProceedingsMaterialTypeName, fields="__all__")
class ProceedingsMaterialTypeName:
    pass

@strawberry.django.type(models.AgendaTypeName, fields="__all__")
class AgendaTypeName:
    pass

@strawberry.django.type(models.AgendaFilterTypeName, fields="__all__")
class AgendaFilterTypeName:
    pass

@strawberry.django.type(models.SessionStatusName, fields="__all__")
class SessionStatusName:
    pass

@strawberry.django.type(models.SessionPurposeName, fields="__all__")
class SessionPurposeName:
    timeslot_types: JSON

@strawberry.django.type(models.TimeSlotTypeName, fields="__all__")
class TimeSlotTypeName:
    pass

@strawberry.django.type(models.ConstraintName, fields="__all__")
class ConstraintName:
    pass

@strawberry.django.type(models.TimerangeName, fields="__all__")
class TimerangeName:
    pass

@strawberry.django.type(models.LiaisonStatementPurposeName, fields="__all__")
class LiaisonStatementPurposeName:
    pass

@strawberry.django.type(models.NomineePositionStateName, fields="__all__")
class NomineePositionStateName:
    pass

@strawberry.django.type(models.FeedbackTypeName, fields="__all__")
class FeedbackTypeName:
    pass

@strawberry.django.type(models.DBTemplateTypeName, fields="__all__")
class DBTemplateTypeName:
    pass

@strawberry.django.type(models.DraftSubmissionStateName, fields="__all__")
class DraftSubmissionStateName:
    pass

@strawberry.django.type(models.RoomResourceName, fields="__all__")
class RoomResourceName:
    pass

@strawberry.django.type(models.IprDisclosureStateName, fields="__all__")
class IprDisclosureStateName:
    pass

@strawberry.django.type(models.IprLicenseTypeName, fields="__all__")
class IprLicenseTypeName:
    pass

@strawberry.django.type(models.IprEventTypeName, fields="__all__")
class IprEventTypeName:
    pass

@strawberry.django.type(models.LiaisonStatementState, fields="__all__")
class LiaisonStatementState:
    pass

@strawberry.django.type(models.LiaisonStatementEventTypeName, fields="__all__")
class LiaisonStatementEventTypeName:
    pass

@strawberry.django.type(models.LiaisonStatementTagName, fields="__all__")
class LiaisonStatementTagName:
    pass

@strawberry.django.type(models.ReviewRequestStateName, fields="__all__")
class ReviewRequestStateName:
    pass

@strawberry.django.type(models.ReviewAssignmentStateName, fields="__all__")
class ReviewAssignmentStateName:
    pass

@strawberry.django.type(models.ReviewTypeName, fields="__all__")
class ReviewTypeName:
    pass

@strawberry.django.type(models.ReviewResultName, fields="__all__")
class ReviewResultName:
    pass

@strawberry.django.type(models.ReviewerQueuePolicyName, fields="__all__")
class ReviewerQueuePolicyName:
    pass

@strawberry.django.type(models.TopicAudienceName, fields="__all__")
class TopicAudienceName:
    pass

@strawberry.django.type(models.ContinentName, fields="__all__")
class ContinentName:
    pass

@strawberry.django.type(models.CountryName, fields="__all__")
class CountryName:
    continent: "ContinentName"

@strawberry.django.type(models.ImportantDateName, fields="__all__")
class ImportantDateName:
    pass

@strawberry.django.type(models.DocUrlTagName, fields="__all__")
class DocUrlTagName:
    pass

@strawberry.django.type(models.ExtResourceTypeName, fields="__all__")
class ExtResourceTypeName:
    pass

@strawberry.django.type(models.ExtResourceName, fields="__all__")
class ExtResourceName:
    type: "ExtResourceTypeName"

@strawberry.django.type(models.SlideSubmissionStatusName, fields="__all__")
class SlideSubmissionStatusName:
    pass

@strawberry.django.type(models.TelechatAgendaSectionName, fields="__all__")
class TelechatAgendaSectionName:
    pass

@strawberry.django.filter(models.GroupStateName)
class GroupStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.GroupTypeName)
class GroupTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.GroupMilestoneStateName)
class GroupMilestoneStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.RoleName)
class RoleNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.StreamName)
class StreamNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DocRelationshipName)
class DocRelationshipNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DocTypeName)
class DocTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DocTagName)
class DocTagNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.StdLevelName)
class StdLevelNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.IntendedStdLevelName)
class IntendedStdLevelNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.FormalLanguageName)
class FormalLanguageNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DocReminderTypeName)
class DocReminderTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.BallotPositionName)
class BallotPositionNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.MeetingTypeName)
class MeetingTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ProceedingsMaterialTypeName)
class ProceedingsMaterialTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.AgendaTypeName)
class AgendaTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.AgendaFilterTypeName)
class AgendaFilterTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.SessionStatusName)
class SessionStatusNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.SessionPurposeName)
class SessionPurposeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto
    timeslot_types: JSON

@strawberry.django.filter(models.TimeSlotTypeName)
class TimeSlotTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ConstraintName)
class ConstraintNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.TimerangeName)
class TimerangeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.LiaisonStatementPurposeName)
class LiaisonStatementPurposeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.NomineePositionStateName)
class NomineePositionStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.FeedbackTypeName)
class FeedbackTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DBTemplateTypeName)
class DBTemplateTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DraftSubmissionStateName)
class DraftSubmissionStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.RoomResourceName)
class RoomResourceNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.IprDisclosureStateName)
class IprDisclosureStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.IprLicenseTypeName)
class IprLicenseTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.IprEventTypeName)
class IprEventTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.LiaisonStatementState)
class LiaisonStatementStateFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.LiaisonStatementEventTypeName)
class LiaisonStatementEventTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.LiaisonStatementTagName)
class LiaisonStatementTagNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ReviewRequestStateName)
class ReviewRequestStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ReviewAssignmentStateName)
class ReviewAssignmentStateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ReviewTypeName)
class ReviewTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ReviewResultName)
class ReviewResultNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ReviewerQueuePolicyName)
class ReviewerQueuePolicyNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.TopicAudienceName)
class TopicAudienceNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ContinentName)
class ContinentNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.CountryName)
class CountryNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto
    continent: "ContinentName"

@strawberry.django.filter(models.ImportantDateName)
class ImportantDateNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.DocUrlTagName)
class DocUrlTagNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ExtResourceTypeName)
class ExtResourceTypeNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.ExtResourceName)
class ExtResourceNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto
    type: "ExtResourceTypeName"


@strawberry.django.filter(models.SlideSubmissionStatusName)
class SlideSubmissionStatusNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

@strawberry.django.filter(models.TelechatAgendaSectionName)
class TelechatAgendaSectionNameFilter:
    slug: auto
    name: auto
    desc: auto
    used: auto
    order: auto

