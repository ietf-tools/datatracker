# Copyright The IETF Trust 2023, All Rights Reserved

from typing import List
import strawberry

from .types import (
    GroupStateName,
    GroupTypeName,
    GroupMilestoneStateName,
    RoleName,
    StreamName,
    DocRelationshipName,
    DocTypeName,
    DocTagName,
    StdLevelName,
    IntendedStdLevelName,
    FormalLanguageName,
    DocReminderTypeName,
    BallotPositionName,
    MeetingTypeName,
    ProceedingsMaterialTypeName,
    AgendaTypeName,
    AgendaFilterTypeName,
    SessionStatusName,
    SessionPurposeName,
    TimeSlotTypeName,
    ConstraintName,
    TimerangeName,
    LiaisonStatementPurposeName,
    NomineePositionStateName,
    FeedbackTypeName,
    DBTemplateTypeName,
    DraftSubmissionStateName,
    RoomResourceName,
    IprDisclosureStateName,
    IprLicenseTypeName,
    IprEventTypeName,
    LiaisonStatementState,
    LiaisonStatementEventTypeName,
    LiaisonStatementTagName,
    ReviewRequestStateName,
    ReviewAssignmentStateName,
    ReviewTypeName,
    ReviewResultName,
    ReviewerQueuePolicyName,
    TopicAudienceName,
    ContinentName,
    CountryName,
    ImportantDateName,
    DocUrlTagName,
    ExtResourceTypeName,
    ExtResourceName,
    SlideSubmissionStatusName,
    TelechatAgendaSectionName,

    GroupStateNameFilter,
    GroupTypeNameFilter,
    GroupMilestoneStateNameFilter,
    RoleNameFilter,
    StreamNameFilter,
    DocRelationshipNameFilter,
    DocTypeNameFilter,
    DocTagNameFilter,
    StdLevelNameFilter,
    IntendedStdLevelNameFilter,
    FormalLanguageNameFilter,
    DocReminderTypeNameFilter,
    BallotPositionNameFilter,
    MeetingTypeNameFilter,
    ProceedingsMaterialTypeNameFilter,
    AgendaTypeNameFilter,
    AgendaFilterTypeNameFilter,
    SessionStatusNameFilter,
    SessionPurposeNameFilter,
    TimeSlotTypeNameFilter,
    ConstraintNameFilter,
    TimerangeNameFilter,
    LiaisonStatementPurposeNameFilter,
    NomineePositionStateNameFilter,
    FeedbackTypeNameFilter,
    DBTemplateTypeNameFilter,
    DraftSubmissionStateNameFilter,
    RoomResourceNameFilter,
    IprDisclosureStateNameFilter,
    IprLicenseTypeNameFilter,
    IprEventTypeNameFilter,
    LiaisonStatementStateFilter,
    LiaisonStatementEventTypeNameFilter,
    LiaisonStatementTagNameFilter,
    ReviewRequestStateNameFilter,
    ReviewAssignmentStateNameFilter,
    ReviewTypeNameFilter,
    ReviewResultNameFilter,
    ReviewerQueuePolicyNameFilter,
    TopicAudienceNameFilter,
    ContinentNameFilter,
    CountryNameFilter,
    ImportantDateNameFilter,
    DocUrlTagNameFilter,
    ExtResourceTypeNameFilter,
    ExtResourceNameFilter,
    SlideSubmissionStatusNameFilter,
    TelechatAgendaSectionNameFilter,
)

@strawberry.type
class Query:
    groupstatenameById: GroupStateName = strawberry.django.field()
    grouptypenameById: GroupTypeName = strawberry.django.field()
    groupmilestonestatenameById: GroupMilestoneStateName = strawberry.django.field()
    rolenameById: RoleName = strawberry.django.field()
    streamnameById: StreamName = strawberry.django.field()
    docrelationshipnameById: DocRelationshipName = strawberry.django.field()
    doctypenameById: DocTypeName = strawberry.django.field()
    doctagnameById: DocTagName = strawberry.django.field()
    stdlevelnameById: StdLevelName = strawberry.django.field()
    intendedstdlevelnameById: IntendedStdLevelName = strawberry.django.field()
    formallanguagenameById: FormalLanguageName = strawberry.django.field()
    docremindertypenameById: DocReminderTypeName = strawberry.django.field()
    ballotpositionnameById: BallotPositionName = strawberry.django.field()
    meetingtypenameById: MeetingTypeName = strawberry.django.field()
    proceedingsmaterialtypenameById: ProceedingsMaterialTypeName = strawberry.django.field()
    agendatypenameById: AgendaTypeName = strawberry.django.field()
    agendafiltertypenameById: AgendaFilterTypeName = strawberry.django.field()
    sessionstatusnameById: SessionStatusName = strawberry.django.field()
    sessionpurposenameById: SessionPurposeName = strawberry.django.field()
    timeslottypenameById: TimeSlotTypeName = strawberry.django.field()
    constraintnameById: ConstraintName = strawberry.django.field()
    timerangenameById: TimerangeName = strawberry.django.field()
    liaisonstatementpurposenameById: LiaisonStatementPurposeName = strawberry.django.field()
    nomineepositionstatenameById: NomineePositionStateName = strawberry.django.field()
    feedbacktypenameById: FeedbackTypeName = strawberry.django.field()
    dbtemplatetypenameById: DBTemplateTypeName = strawberry.django.field()
    draftsubmissionstatenameById: DraftSubmissionStateName = strawberry.django.field()
    roomresourcenameById: RoomResourceName = strawberry.django.field()
    iprdisclosurestatenameById: IprDisclosureStateName = strawberry.django.field()
    iprlicensetypenameById: IprLicenseTypeName = strawberry.django.field()
    ipreventtypenameById: IprEventTypeName = strawberry.django.field()
    liaisonstatementstateById: LiaisonStatementState = strawberry.django.field()
    liaisonstatementeventtypenameById: LiaisonStatementEventTypeName = strawberry.django.field()
    liaisonstatementtagnameById: LiaisonStatementTagName = strawberry.django.field()
    reviewrequeststatenameById: ReviewRequestStateName = strawberry.django.field()
    reviewassignmentstatenameById: ReviewAssignmentStateName = strawberry.django.field()
    reviewtypenameById: ReviewTypeName = strawberry.django.field()
    reviewresultnameById: ReviewResultName = strawberry.django.field()
    reviewerqueuepolicynameById: ReviewerQueuePolicyName = strawberry.django.field()
    topicaudiencenameById: TopicAudienceName = strawberry.django.field()
    continentnameById: ContinentName = strawberry.django.field()
    countrynameById: CountryName = strawberry.django.field()
    importantdatenameById: ImportantDateName = strawberry.django.field()
    docurltagnameById: DocUrlTagName = strawberry.django.field()
    extresourcetypenameById: ExtResourceTypeName = strawberry.django.field()
    extresourcenameById: ExtResourceName = strawberry.django.field()
    slidesubmissionstatusnameById: SlideSubmissionStatusName = strawberry.django.field()
    telechatagendasectionnameById: TelechatAgendaSectionName = strawberry.django.field()

    groupstatenames: List[GroupStateName] = strawberry.django.field(pagination=True, filters=GroupStateNameFilter)
    grouptypenames: List[GroupTypeName] = strawberry.django.field(pagination=True, filters=GroupTypeNameFilter)
    groupmilestonestatenames: List[GroupMilestoneStateName] = strawberry.django.field(pagination=True, filters=GroupMilestoneStateNameFilter)
    rolenames: List[RoleName] = strawberry.django.field(pagination=True, filters=RoleNameFilter)
    streamnames: List[StreamName] = strawberry.django.field(pagination=True, filters=StreamNameFilter)
    docrelationshipnames: List[DocRelationshipName] = strawberry.django.field(pagination=True, filters=DocRelationshipNameFilter)
    doctypenames: List[DocTypeName] = strawberry.django.field(pagination=True, filters=DocTypeNameFilter)
    doctagnames: List[DocTagName] = strawberry.django.field(pagination=True, filters=DocTagNameFilter)
    stdlevelnames: List[StdLevelName] = strawberry.django.field(pagination=True, filters=StdLevelNameFilter)
    intendedstdlevelnames: List[IntendedStdLevelName] = strawberry.django.field(pagination=True, filters=IntendedStdLevelNameFilter)
    formallanguagenames: List[FormalLanguageName] = strawberry.django.field(pagination=True, filters=FormalLanguageNameFilter)
    docremindertypenames: List[DocReminderTypeName] = strawberry.django.field(pagination=True, filters=DocReminderTypeNameFilter)
    ballotpositionnames: List[BallotPositionName] = strawberry.django.field(pagination=True, filters=BallotPositionNameFilter)
    meetingtypenames: List[MeetingTypeName] = strawberry.django.field(pagination=True, filters=MeetingTypeNameFilter)
    proceedingsmaterialtypenames: List[ProceedingsMaterialTypeName] = strawberry.django.field(pagination=True, filters=ProceedingsMaterialTypeNameFilter)
    agendatypenames: List[AgendaTypeName] = strawberry.django.field(pagination=True, filters=AgendaTypeNameFilter)
    agendafiltertypenames: List[AgendaFilterTypeName] = strawberry.django.field(pagination=True, filters=AgendaFilterTypeNameFilter)
    sessionstatusnames: List[SessionStatusName] = strawberry.django.field(pagination=True, filters=SessionStatusNameFilter)
    sessionpurposenames: List[SessionPurposeName] = strawberry.django.field(pagination=True, filters=SessionPurposeNameFilter)
    timeslottypenames: List[TimeSlotTypeName] = strawberry.django.field(pagination=True, filters=TimeSlotTypeNameFilter)
    constraintnames: List[ConstraintName] = strawberry.django.field(pagination=True, filters=ConstraintNameFilter)
    timerangenames: List[TimerangeName] = strawberry.django.field(pagination=True, filters=TimerangeNameFilter)
    liaisonstatementpurposenames: List[LiaisonStatementPurposeName] = strawberry.django.field(pagination=True, filters=LiaisonStatementPurposeNameFilter)
    nomineepositionstatenames: List[NomineePositionStateName] = strawberry.django.field(pagination=True, filters=NomineePositionStateNameFilter)
    feedbacktypenames: List[FeedbackTypeName] = strawberry.django.field(pagination=True, filters=FeedbackTypeNameFilter)
    dbtemplatetypenames: List[DBTemplateTypeName] = strawberry.django.field(pagination=True, filters=DBTemplateTypeNameFilter)
    draftsubmissionstatenames: List[DraftSubmissionStateName] = strawberry.django.field(pagination=True, filters=DraftSubmissionStateNameFilter)
    roomresourcenames: List[RoomResourceName] = strawberry.django.field(pagination=True, filters=RoomResourceNameFilter)
    iprdisclosurestatenames: List[IprDisclosureStateName] = strawberry.django.field(pagination=True, filters=IprDisclosureStateNameFilter)
    iprlicensetypenames: List[IprLicenseTypeName] = strawberry.django.field(pagination=True, filters=IprLicenseTypeNameFilter)
    ipreventtypenames: List[IprEventTypeName] = strawberry.django.field(pagination=True, filters=IprEventTypeNameFilter)
    liaisonstatementstates: List[LiaisonStatementState] = strawberry.django.field(pagination=True, filters=LiaisonStatementStateFilter)
    liaisonstatementeventtypenames: List[LiaisonStatementEventTypeName] = strawberry.django.field(pagination=True, filters=LiaisonStatementEventTypeNameFilter)
    liaisonstatementtagnames: List[LiaisonStatementTagName] = strawberry.django.field(pagination=True, filters=LiaisonStatementTagNameFilter)
    reviewrequeststatenames: List[ReviewRequestStateName] = strawberry.django.field(pagination=True, filters=ReviewRequestStateNameFilter)
    reviewassignmentstatenames: List[ReviewAssignmentStateName] = strawberry.django.field(pagination=True, filters=ReviewAssignmentStateNameFilter)
    reviewtypenames: List[ReviewTypeName] = strawberry.django.field(pagination=True, filters=ReviewTypeNameFilter)
    reviewresultnames: List[ReviewResultName] = strawberry.django.field(pagination=True, filters=ReviewResultNameFilter)
    reviewerqueuepolicynames: List[ReviewerQueuePolicyName] = strawberry.django.field(pagination=True, filters=ReviewerQueuePolicyNameFilter)
    topicaudiencenames: List[TopicAudienceName] = strawberry.django.field(pagination=True, filters=TopicAudienceNameFilter)
    continentnames: List[ContinentName] = strawberry.django.field(pagination=True, filters=ContinentNameFilter)
    countrynames: List[CountryName] = strawberry.django.field(pagination=True, filters=CountryNameFilter)
    importantdatenames: List[ImportantDateName] = strawberry.django.field(pagination=True, filters=ImportantDateNameFilter)
    docurltagnames: List[DocUrlTagName] = strawberry.django.field(pagination=True, filters=DocUrlTagNameFilter)
    extresourcetypenames: List[ExtResourceTypeName] = strawberry.django.field(pagination=True, filters=ExtResourceTypeNameFilter)
    extresourcenames: List[ExtResourceName] = strawberry.django.field(pagination=True, filters=ExtResourceNameFilter)
    slidesubmissionstatusnames: List[SlideSubmissionStatusName] = strawberry.django.field(pagination=True, filters=SlideSubmissionStatusNameFilter)
    telechatagendasectionnames: List[TelechatAgendaSectionName] = strawberry.django.field(pagination=True, filters=TelechatAgendaSectionNameFilter)

schema = strawberry.Schema(
    Query
)
