import datetime

from django.db import models

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.person.models import Person, Email
from ietf.name.models import ReviewTypeName, ReviewRequestStateName, ReviewResultName

class ReviewerSettings(models.Model):
    """Keeps track of admin data associated with the reviewer in the
    particular team. There will be one record for each combination of
    reviewer and team."""
    team        = models.ForeignKey(Group)
    person      = models.ForeignKey(Person)
    INTERVALS = [
        (7, "Once per week"),
        (14, "Once per fortnight"),
        (30, "Once per month"),
        (61, "Once per two months"),
        (91, "Once per quarter"),
    ]
    min_interval = models.IntegerField(default=30, verbose_name="Can review at most", choices=INTERVALS)
    filter_re   = models.CharField(max_length=255, verbose_name="Filter regexp", blank=True, help_text="Draft names matching regular expression should not be assigned")
    skip_next   = models.IntegerField(default=0, verbose_name="Skip next assignments")

    def __unicode__(self):
        return u"{} in {}".format(self.person, self.team)

class UnavailablePeriod(models.Model):
    team         = models.ForeignKey(Group)
    person       = models.ForeignKey(Person)
    start_date   = models.DateField(default=datetime.date.today, help_text="Choose the start date so that you can still do a review if it's assigned just before the start date - this usually means you should mark yourself unavailable for assignment some time before you are actually away.")
    end_date     = models.DateField(blank=True, null=True, help_text="Leaving the end date blank means that the period continues indefinitely. You can end it later.")
    AVAILABILITY_CHOICES = [
        ("canfinish", "Can do follow-ups"),
        ("unavailable", "Completely unavailable"),
    ]
    LONG_AVAILABILITY_CHOICES = [
        ("canfinish", "Can do follow-up reviews and finish outstanding reviews"),
        ("unavailable", "Completely unavailable - reassign any outstanding reviews"),
    ]
    availability = models.CharField(max_length=30, choices=AVAILABILITY_CHOICES)

    def state(self):
        import datetime
        today = datetime.date.today()
        if self.start_date <= today:
            if not self.end_date or today <= self.end_date:
                return "active"
            else:
                return "past"
        else:
            return "future"

    def __unicode__(self):
        return u"{} is unavailable in {} {} - {}".format(self.person, self.team.acronym, self.start_date, self.end_date or "")

class ReviewWish(models.Model):
    """Reviewer wishes to review a document when it becomes available for review."""
    time        = models.DateTimeField(default=datetime.datetime.now)
    team        = models.ForeignKey(Group)
    person      = models.ForeignKey(Person)
    doc         = models.ForeignKey(Document)

    def __unicode__(self):
        return u"{} wishes to review {} in {}".format(self.person, self.doc.name, self.team.acronym)
    
class ReviewTeamResult(models.Model):
    """Captures that a result name is valid for a given team for new
    reviews. This also implicitly defines which teams are review
    teams - if there are no possible review results valid for a given
    team, it can't be a review team."""
    team        = models.ForeignKey(Group)
    result      = models.ForeignKey(ReviewResultName)

    def __unicode__(self):
        return u"{} in {}".format(self.result.name, self.group.acronym)

class ReviewRequest(models.Model):
    """Represents a request for a review and the process it goes through.
    There should be one ReviewRequest entered for each combination of
    document, rev, and reviewer."""
    state         = models.ForeignKey(ReviewRequestStateName)

    old_id        = models.IntegerField(blank=True, null=True, help_text="ID in previous review system") # FIXME: remove this when everything has been migrated

    # Fields filled in on the initial record creation - these
    # constitute the request part.
    time          = models.DateTimeField(default=datetime.datetime.now)
    type          = models.ForeignKey(ReviewTypeName)
    doc           = models.ForeignKey(Document, related_name='review_request_set')
    team          = models.ForeignKey(Group, limit_choices_to=~models.Q(reviewteamresult=None))
    deadline      = models.DateField()
    requested_by  = models.ForeignKey(Person)
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
