# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone

from ietf.doc.models import Document
from ietf.name.models import (
    DocRelationshipName,
    StdLevelName,
    StreamName,
    SourceFormatName,
    TlpBoilerplateChoiceName,
)
from ietf.person.models import Person


class RfcToBe(models.Model):
    """RPC representation of a pre-publication RFC

    Notes:
     * not in_progress and not published = abandoned without publication
    """

    in_progress = models.BooleanField(default=True)
    published = models.DateTimeField(
        null=True
    )  # should match a DocEvent on the rfc Document
    is_april_first_rfc = models.BooleanField(default=False)
    draft = models.ForeignKey(
        Document, null=True, on_delete=models.PROTECT
    )  # only null if is_april_first_rfc is True
    rfc_number = models.PositiveIntegerField(null=True)

    cluster = models.ForeignKey("Cluster", null=True, on_delete=models.SET_NULL)
    order_in_cluster = models.PositiveSmallIntegerField(default=1)

    submitted_format = models.ForeignKey(SourceFormatName, on_delete=models.PROTECT)
    submitted_std_level = models.ForeignKey(
        StdLevelName, on_delete=models.PROTECT, related_name="+"
    )
    submitted_boilerplate = models.ForeignKey(
        TlpBoilerplateChoiceName, on_delete=models.PROTECT, related_name="+"
    )
    submitted_stream = models.ForeignKey(
        StreamName, on_delete=models.PROTECT, related_name="+"
    )

    intended_std_level = models.ForeignKey(
        StdLevelName, on_delete=models.PROTECT, related_name="+"
    )
    intended_boilerplate = models.ForeignKey(
        TlpBoilerplateChoiceName, on_delete=models.PROTECT, related_name="+"
    )
    intended_stream = models.ForeignKey(
        StreamName, on_delete=models.PROTECT, related_name="+"
    )

    external_deadline = models.DateTimeField(null=True)
    internal_goal = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(draft__isnull=False) ^ models.Q(is_april_first_rfc=True),
                name="rfctobe_draft_not_null_xor_is_april_first_rfc",
                violation_error_message="draft must be null if and only if is_april_first_rfc",
            ),
            models.UniqueConstraint(
                fields=["cluster", "order_in_cluster"],
                name="rfctobe_unique_order_in_cluster",
                violation_error_message="order in cluster must be unique",
                deferrable=models.Deferrable.DEFERRED,
            ),
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
    ("assigned", "assigned"),
    ("in progress", "in progress"),
    ("done", "done"),
)


class Assignment(models.Model):
    """Assignment of an RpcPerson to an RfcToBe"""

    rfc_to_be = models.ForeignKey(RfcToBe, on_delete=models.PROTECT)
    person = models.ForeignKey(RpcPerson, on_delete=models.PROTECT)
    state = models.CharField(
        max_length=32, choices=ASSIGNMENT_STATE_CHOICES, default="assigned"
    )
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
    requested = models.DateTimeField(default=timezone.now)
    approved = models.DateTimeField(null=True)


class ActionHolder(models.Model):
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    since_when = models.DateTimeField(default=timezone.now)
    completed = models.DateTimeField(null=True)
    comment = models.TextField(blank=True)


class RpcRelatedDocument(models.Model):
    """Relationship between an RFC-to-be and a draft, RFC, or RFC-to-be

    rtb = RfcToBe.objects.get(...)  # or Document.objects.get(...)
    rtb.rpcrelateddocument_set.all()  # relationships where rtb is source
    rtb.rpcrelateddocument_target_set()  # relationships where rtb is target
    """

    relationship = models.ForeignKey(DocRelationshipName, on_delete=models.PROTECT)
    source = models.ForeignKey(RfcToBe, on_delete=models.PROTECT)
    target_document = models.ForeignKey(
        Document,
        null=True,
        on_delete=models.PROTECT,
        related_name="rpcrelateddocument_target_set",
    )
    target_rfctobe = models.ForeignKey(
        RfcToBe,
        null=True,
        on_delete=models.PROTECT,
        related_name="rpcrelateddocument_target_set",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(target_document__isnull=True)
                    ^ models.Q(target_rfctobe__isnull=True)
                ),
                name="rpcrelateddocument_exactly_one_target",
                violation_error_message="exactly one target field must be set",
            )
        ]


class RpcDocumentComment(models.Model):
    """Private RPC comment about a draft, RFC or RFC-to-be"""

    document = models.ForeignKey(Document, null=True, on_delete=models.PROTECT)
    rfc_to_be = models.ForeignKey(RfcToBe, null=True, on_delete=models.PROTECT)
    comment = models.TextField()
    by = models.ForeignKey(Person, on_delete=models.PROTECT)
    time = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(document__isnull=True)
                ^ models.Q(rfc_to_be__isnull=True),
                name="rpcdocumentcomment_exactly_one_target",
                violation_error_message="exactly one of document or rfc_to_be must be set",
            )
        ]


class RpcAuthorComment(models.Model):
    """Private RPC comment about an author

    Notes:
        rjs = Person(...)
        rjs.rpcauthorcomments_by.all()  # comments by
        rjs.rpcauthorcomment_set.all()  # comments about
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    comment = models.TextField()
    by = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="rpcauthorcomments_by"
    )
    time = models.DateTimeField(default=timezone.now)
