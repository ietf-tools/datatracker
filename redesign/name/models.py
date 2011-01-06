# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

class NameModel(models.Model):
    slug = models.CharField(max_length=8, primary_key=True)
    name = models.CharField(max_length=32)
    desc = models.TextField(blank=True)
    used = models.BooleanField(default=True)

    def __unicode__(self):
        return self.name
    
    class Meta:
        abstract = True

class GroupStateName(NameModel):
    """BOF, Proposed, Active, Dormant, Concluded"""
class GroupTypeName(NameModel):
    """IETF, Area, WG, RG, Team, etc."""
class RoleName(NameModel):
    """AD, Chair"""
class DocStreamName(NameModel):
    """IETF, IAB, IRTF, Independent Submission, Legacy"""
class DocStateName(NameModel):
    """Active, Expired, RFC, Replaced, Withdrawn"""
class DocRelationshipName(NameModel):
    """Updates, Replaces, Obsoletes, Reviews, ... The relationship is
    always recorded in one direction.
    """
class WgDocStateName(NameModel):
    """Not, Candidate, Active, Parked, LastCall, WriteUp, Submitted,
    Dead"""
class IesgDocStateName(NameModel):
    """Pub Request, Ad Eval, Expert Review, Last Call Requested, In
    Last Call, Waiting for Writeup, Waiting for AD Go-Ahead, IESG
    Evaluation, Deferred, Approved, Announcement Sent, Do Not Publish,
    Ad is watching, Dead """
class IanaDocStateName(NameModel):
    """ """
class RfcDocStateName(NameModel):
    """Missref, Edit, RFC-Editor, Auth48, Auth, Published; ISR,
    ISR-Auth, ISR-Timeout;"""
class DocTypeName(NameModel):
    """Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email,
    Review, Issue, Wiki"""
class DocInfoTagName(NameModel):
    """Waiting for Reference, IANA Coordination, Revised ID Needed,
    External Party, AD Followup, Point Raised - Writeup Needed"""
class StdLevelName(NameModel):
    """Proposed Standard, Draft Standard, Standard, Experimental,
    Informational, Best Current Practice, Historic, ..."""
class IntendedStdLevelName(NameModel):
    """Standards Track, Experimental, Informational, Best Current
    Practice, Historic, ..."""
class BallotPositionName(NameModel):
    """ Yes, NoObjection, Abstain, Discuss, Recuse """
