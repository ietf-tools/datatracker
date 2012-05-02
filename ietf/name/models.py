# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

class NameModel(models.Model):
    slug = models.CharField(max_length=8, primary_key=True)
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True)
    used = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name
    
    class Meta:
        abstract = True
        ordering = ['order']

class GroupStateName(NameModel):
    """BOF, Proposed, Active, Dormant, Concluded"""
class GroupTypeName(NameModel):
    """IETF, Area, WG, RG, Team, etc."""
class RoleName(NameModel):
    """AD, Chair"""
class StreamName(NameModel):
    """IETF, IAB, IRTF, ISE, Legacy"""
class DocRelationshipName(NameModel):
    """Updates, Replaces, Obsoletes, Reviews, ... The relationship is
    always recorded in one direction."""
class DocTypeName(NameModel):
    """Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email,
    Review, Issue, Wiki"""
class DocTagName(NameModel):
    """Waiting for Reference, IANA Coordination, Revised ID Needed,
    External Party, AD Followup, Point Raised - Writeup Needed, ..."""
class StdLevelName(NameModel):
    """Proposed Standard, (Draft Standard), Internet Standard, Experimental,
    Informational, Best Current Practice, Historic, ..."""
class IntendedStdLevelName(NameModel):
    """Proposed Standard, (Draft Standard), Internet Standard, Experimental,
    Informational, Best Current Practice, Historic, ..."""
class DocReminderTypeName(NameModel):
    "Stream state"
class BallotPositionName(NameModel):
    """ Yes, No Objection, Abstain, Discuss, Block, Recuse """
    blocking = models.BooleanField(default=False)
class GroupBallotPositionName(NameModel):
    """ Yes, No, Block, Abstain """
class MeetingTypeName(NameModel):
    """IETF, Interim"""
class SessionStatusName(NameModel):
    """Waiting for Approval, Approved, Waiting for Scheduling, Scheduled, Cancelled, Disapproved"""
class TimeSlotTypeName(NameModel):
    """Session, Break, Registration"""
class ConstraintName(NameModel):
    """Conflict"""
class LiaisonStatementPurposeName(NameModel):
    """For action, For comment, For information, In response, Other"""
