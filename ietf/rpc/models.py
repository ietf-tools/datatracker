from django.db import models

from ietf.doc.models import Document
from ietf.name.models import StdLevelName, StreamName, SourceFormatName, TlpBoilerplateChoiceName
from ietf.person.models import Person


class RfcToBe(models.Model):
    """
    
    Notes:
     * not in_progress and not published = abandoned without publication
    """
    in_progress = models.BooleanField(default=True)
    published = models.DateTimeField(null=True)  # should match a DocEvent on the rfc Document
    is_april_first_rfc = models.BooleanField(default=False)
    draft = models.ForeignKey(Document, null=True, on_delete=models.PROTECT)  # only null if is_april_first_rfc is True
    cluster = models.ForeignKey("Cluster", null=True, on_delete=models.SET_NULL)
    rfc_number = models.PositiveIntegerField()

    submitted_format = models.ForeignKey(SourceFormatName, on_delete=models.PROTECT)
    submitted_std_level = models.ForeignKey(StdLevelName, on_delete=models.PROTECT)
    submitted_boilerplate = models.ForeignKey(TlpBoilerplateChoiceName, on_delete=models.PROTECT)
    submitted_stream = models.ForeignKey(StreamName, on_delete=models.PROTECT)

    intended_std_level = models.ForeignKey(StdLevelName, on_delete=models.PROTECT)
    intended_boilerplate = models.ForeignKey(TlpBoilerplateChoiceName, on_delete=models.PROTECT)
    intended_stream = models.ForeignKey(StreamName, on_delete=models.PROTECT)

    external_deadline = models.DateTimeField(null=True)
    internal_goal = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(draft__isnull=False) ^ models.Q(is_april_first_rfc=True),
                name="draft_not_null_xor_is_april_first_rfc",
                violation_error_message="draft must be null if and only if is_april_first_rfc",
            )
        ]

    
class Cluster(models.Model):
    number = models.PositiveIntegerField(unique=True)


class UnusableRfcNumber:
    number = models.PositiveIntegerField(primary_key=True)
    comment = models.TextField(blank=True)


class RpcPerson(models.Model):
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    can_hold_role = models.ManyToManyField("RpcRole")
    capable_of = models.ManyToManyField("Capability")


ASSIGNMENT_STATE_CHOICES = (
    ("unassigned", "unassigned"),
    ("assigned", "assigned"),
    ("in progress", "in progress"),
    ("done", "done"),
)


class Assignment(models.Model):
    """Assignment of an RpcPerson to an RfcToBe"""
    rfc_to_be = models.ForeignKey(RfcToBe, on_delete=models.PROTECT)
    person = models.ForeignKey(RpcPerson, on_delete=models.PROTECT)
    state = models.CharField(max_length=32, choices=ASSIGNMENT_STATE_CHOICES, default="unassigned")
    time_spent = models.DurationField()  # tbd


class RpcRole(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True)
    # todo populate


class Capability(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True)
    # todo populate


class RfcAuthor(models.Model):
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    rfc_to_be = models.ForeignKey(RfcToBe, on_delete=models.PROTECT)
    auth48_approved = models.DateTimeField(null=True)


class FinalApproval(models.Model):
    rfc_to_be = models.ForeignKey(RfcToBe, on_delete=models.PROTECT)
    approver = models.ForeignKey(Person, on_delete=models.PROTECT)
    requested = models.DateTimeField(auto_now=True)
    approved = models.DateTimeField(null=True)
