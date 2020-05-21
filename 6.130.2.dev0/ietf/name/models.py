# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import models

from ietf.utils.models import ForeignKey

class NameModel(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True)
    used = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        ordering = ['order', 'name']

class GroupStateName(NameModel):
    """BOF, Proposed, Active, Dormant, Concluded, Abandoned"""
class GroupTypeName(NameModel):
    """IETF, Area, WG, RG, Team, etc."""
    verbose_name = models.CharField(max_length=255, default="")
class GroupMilestoneStateName(NameModel):
    """Active, Deleted, For Review, Chartering"""
class RoleName(NameModel):
    """AD, Chair"""
class StreamName(NameModel):
    """IETF, IAB, IRTF, ISE, Legacy"""

class DocRelationshipName(NameModel):
    """Updates, Replaces, Obsoletes, Reviews, ... The relationship is
    always recorded in one direction."""
    revname = models.CharField(max_length=255)

class DocTypeName(NameModel):
    """Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email,
    Review, Issue, Wiki"""
    prefix =  models.CharField(max_length=16, default="")
class DocTagName(NameModel):
    """Waiting for Reference, IANA Coordination, Revised ID Needed,
    External Party, AD Followup, Point Raised - Writeup Needed, ..."""
class StdLevelName(NameModel):
    """Proposed Standard, (Draft Standard), Internet Standard, Experimental,
    Informational, Best Current Practice, Historic, ..."""
class IntendedStdLevelName(NameModel):
    """Proposed Standard, (Draft Standard), Internet Standard, Experimental,
    Informational, Best Current Practice, Historic, ..."""
class FormalLanguageName(NameModel):
    """ABNF, ASN.1, C code, CBOR, JSON, XML, ..."""
class DocReminderTypeName(NameModel):
    "Stream state"
class BallotPositionName(NameModel):
    """ Yes, No Objection, Abstain, Discuss, Block, Recuse, Need More Time,
    Not Ready """
    blocking = models.BooleanField(default=False)
class MeetingTypeName(NameModel):
    """IETF, Interim"""
class AgendaTypeName(NameModel):
    """ietf, ad, side, workshop, ..."""
class SessionStatusName(NameModel):
    """Waiting for Approval, Approved, Waiting for Scheduling, Scheduled, Cancelled, Disapproved"""
class TimeSlotTypeName(NameModel):
    """Session, Break, Registration, Other, Reserved, unavail"""
class ConstraintName(NameModel):
    """conflict, conflic2, conflic3, bethere, timerange, time_relation, wg_adjacent"""
    penalty = models.IntegerField(default=0, help_text="The penalty for violating this kind of constraint; for instance 10 (small penalty) or 10000 (large penalty)")
    editor_label = models.CharField(max_length=32, blank=True, help_text="Very short label for producing warnings inline in the sessions in the schedule editor.")
class TimerangeName(NameModel):
    """(monday|tuesday|wednesday|thursday|friday)-(morning|afternoon-early|afternoon-late)"""
class LiaisonStatementPurposeName(NameModel):
    """For action, For comment, For information, In response, Other"""
class NomineePositionStateName(NameModel):
    """Status of a candidate for a position: None, Accepted, Declined"""
class FeedbackTypeName(NameModel):
    """Type of feedback: questionnaires, nominations, comments"""
class DBTemplateTypeName(NameModel):
    """reStructuredText, Plain, Django"""
class DraftSubmissionStateName(NameModel):
    """Uploaded, Awaiting Submitter Authentication, Awaiting Approval from
    Previous Version Authors, Awaiting Initial Version Approval, Awaiting
    Manual Post, Cancelled, Posted"""
    next_states = models.ManyToManyField('DraftSubmissionStateName', related_name="previous_states", blank=True)
class RoomResourceName(NameModel):
    "Room resources: Audio Stream, Meetecho, . . ."
class IprDisclosureStateName(NameModel):
    """Pending, Parked, Posted, Rejected, Removed"""
class IprLicenseTypeName(NameModel):
    """choices a-f from the current form made admin maintainable"""
class IprEventTypeName(NameModel):
    """submitted,posted,parked,removed,rejected,msgin,msgoutcomment,private_comment,
    legacy,update_notify,change_disclosure"""
class LiaisonStatementState(NameModel):
    "Pending, Approved, Dead"
class LiaisonStatementEventTypeName(NameModel):
    "Submitted, Modified, Approved, Posted, Killed, Resurrected, MsgIn, MsgOut, Comment"
class LiaisonStatementTagName(NameModel):
    "Action Required, Action Taken"
class ReviewRequestStateName(NameModel):
    """Requested, Assigned, Withdrawn, Overtaken By Events, No Review of Version, No Review of Document"""
class ReviewAssignmentStateName(NameModel):
    """Accepted, Rejected, Withdrawn, Overtaken By Events, No Response, Partially Completed, Completed"""
class ReviewTypeName(NameModel):
    """Early Review, Last Call, Telechat"""
class ReviewResultName(NameModel):
    """Almost ready, Has issues, Has nits, Not Ready,
    On the right track, Ready, Ready with issues,
    Ready with nits, Serious Issues"""
class ReviewerQueuePolicyName(NameModel):
    """RotateAlphabetically, LeastRecentlyUsed"""
class TopicAudienceName(NameModel):
    """General, Nominee, Nomcom Member"""
class ContinentName(NameModel):
    "Africa, Antarctica, Asia, ..."
class CountryName(NameModel):
    "Afghanistan, Aaland Islands, Albania, ..."
    continent = ForeignKey(ContinentName)
    in_eu = models.BooleanField(verbose_name="In EU", default=False)
class ImportantDateName(NameModel):
    "Registration Opens, Scheduling Opens, ID Cutoff, ..."
    default_offset_days = models.SmallIntegerField()
class DocUrlTagName(NameModel):
    "Repository, Wiki, Issue Tracker, ..."
    
