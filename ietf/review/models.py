from django.db import models

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.person.models import Person, Email
from ietf.name.models import ReviewTypeName, ReviewRequestStateName, ReviewResultName

class Reviewer(models.Model):
    """Keeps track of admin data associated with the reviewer in the
    particular team. There will be one record for each combination of
    reviewer and team."""
    team        = models.ForeignKey(Group)
    person      = models.ForeignKey(Person)
    frequency   = models.IntegerField(default=30, help_text="Can review every N days")
    unavailable_until = models.DateTimeField(blank=True, null=True, help_text="When will this reviewer be available again")
    filter_re   = models.CharField(max_length=255, blank=True)
    skip_next   = models.IntegerField(default=0, help_text="Skip the next N review assignments")

    def __unicode__(self):
        return "{} in {}".format(self.person, self.team)

class ReviewTeamResult(models.Model):
     """Captures that a result name is valid for a given team for new
     reviews. This also implicitly defines which teams are review
     teams - if there are no possible review results valid for a given
     team, it can't be a review team."""
     team        = models.ForeignKey(Group)
     result      = models.ForeignKey(ReviewResultName)

class ReviewRequest(models.Model):
    """Represents a request for a review and the process it goes through.
    There should be one ReviewRequest entered for each combination of
    document, rev, and reviewer."""
    state         = models.ForeignKey(ReviewRequestStateName)

    old_id        = models.IntegerField(blank=True, null=True, help_text="ID in previous review system") # FIXME: remove this when everything has been migrated

    # Fields filled in on the initial record creation - these
    # constitute the request part.
    time          = models.DateTimeField(auto_now_add=True)
    type          = models.ForeignKey(ReviewTypeName)
    doc           = models.ForeignKey(Document, related_name='review_request_set')
    team          = models.ForeignKey(Group, limit_choices_to=~models.Q(reviewteamresult=None))
    deadline      = models.DateTimeField()
    requested_rev = models.CharField(verbose_name="requested revision", max_length=16, blank=True, help_text="Fill in if a specific revision is to be reviewed, e.g. 02")

    # Fields filled in as reviewer is assigned and as the review is
    # uploaded. Once these are filled in and we progress beyond being
    # requested/assigned, any changes to the assignment happens by
    # closing down the current request and making a new one, copying
    # the request-part fields above.
    reviewer      = models.ForeignKey(Email, blank=True, null=True)

    review        = models.OneToOneField(Document, blank=True, null=True)
    reviewed_rev  = models.CharField(verbose_name="reviewed revision", max_length=16, blank=True)
    result        = models.ForeignKey(ReviewResultName, blank=True, null=True)

    def __unicode__(self):
        return u"%s review on %s by %s %s" % (self.type, self.doc, self.team, self.state)
