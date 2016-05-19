from django.db import models

from ietf.doc.models import Document
from ietf.group.models import Group, Role
from ietf.name.models import ReviewTypeName, ReviewRequestStateName, ReviewResultName

class Reviewer(models.Model):
    """
    These records associate reviewers with review teams and keep track
    of admin data associated with the reviewer in the particular team.
    There will be one record for each combination of reviewer and team.
    """
    role        = models.ForeignKey(Role)
    frequency   = models.IntegerField(help_text="Can review every N days")
    available   = models.DateTimeField(blank=True, null=True, help_text="When will this reviewer be available again")
    filter_re   = models.CharField(max_length=255, blank=True)
    skip_next   = models.IntegerField(help_text="Skip the next N review assignments")

class ReviewRequest(models.Model):
    """
    There should be one ReviewRequest entered for each combination of
    document, rev, and reviewer.
    """
    # Fields filled in on the initial record creation:
    time          = models.DateTimeField(auto_now_add=True)
    type          = models.ForeignKey(ReviewTypeName)
    doc           = models.ForeignKey(Document, related_name='review_request_set')
    team          = models.ForeignKey(Group)
    deadline      = models.DateTimeField()
    requested_rev = models.CharField(verbose_name="requested revision", max_length=16, blank=True, help_text="Fill in if a specific revision is to be reviewed, e.g. 02")
    state         = models.ForeignKey(ReviewRequestStateName)
    # Fields filled in as reviewer is assigned, and as the review
    # is uploaded
    reviewer      = models.ForeignKey(Reviewer, blank=True, null=True)
    review        = models.OneToOneField(Document, blank=True, null=True)
    reviewed_rev  = models.CharField(verbose_name="reviewed revision", max_length=16, blank=True)
    result        = models.ForeignKey(ReviewResultName, blank=True, null=True)

    def __unicode__(self):
        return u"%s review on %s by %s %s" % (self.type, self.doc, self.team, self.state)
