# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.constraints
import django.db.models.deletion
import django.utils.timezone
import simple_history.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("doc", "0006_statements"),
        ("person", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("name", "0009_populate_tlpboilerplatechoicename"),
    ]

    operations = [
        migrations.CreateModel(
            name="Capability",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Cluster",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("number", models.PositiveIntegerField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="Disposition",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="RfcToBe",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_april_first_rfc", models.BooleanField(default=False)),
                ("rfc_number", models.PositiveIntegerField(null=True)),
                ("order_in_cluster", models.PositiveSmallIntegerField(default=1)),
                ("external_deadline", models.DateTimeField(null=True)),
                ("internal_goal", models.DateTimeField(null=True)),
                (
                    "cluster",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="rpc.cluster",
                    ),
                ),
                (
                    "disposition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rpc.disposition",
                    ),
                ),
                (
                    "draft",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="doc.document",
                    ),
                ),
                (
                    "intended_boilerplate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.tlpboilerplatechoicename",
                    ),
                ),
                (
                    "intended_std_level",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.stdlevelname",
                    ),
                ),
                (
                    "intended_stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.streamname",
                    ),
                ),
                (
                    "submitted_boilerplate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.tlpboilerplatechoicename",
                    ),
                ),
                (
                    "submitted_format",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="name.sourceformatname",
                    ),
                ),
                (
                    "submitted_std_level",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.stdlevelname",
                    ),
                ),
                (
                    "submitted_stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="name.streamname",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RpcRole",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="UnusableRfcNumber",
            fields=[
                (
                    "number",
                    models.PositiveIntegerField(primary_key=True, serialize=False),
                ),
                ("comment", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="RpcRelatedDocument",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "relationship",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="name.docrelationshipname",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="rpc.rfctobe"
                    ),
                ),
                (
                    "target_document",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rpcrelateddocument_target_set",
                        to="doc.document",
                    ),
                ),
                (
                    "target_rfctobe",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rpcrelateddocument_target_set",
                        to="rpc.rfctobe",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RpcPerson",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("can_hold_role", models.ManyToManyField(to="rpc.rpcrole")),
                ("capable_of", models.ManyToManyField(to="rpc.capability")),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RpcDocumentComment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("comment", models.TextField()),
                ("time", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="doc.document",
                    ),
                ),
                (
                    "rfc_to_be",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rpc.rfctobe",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RpcAuthorComment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("comment", models.TextField()),
                ("time", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rpcauthorcomments_by",
                        to="person.person",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RfcAuthor",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("auth48_approved", models.DateTimeField(null=True)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
                (
                    "rfc_to_be",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="rpc.rfctobe"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HistoricalRfcToBe",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("is_april_first_rfc", models.BooleanField(default=False)),
                ("rfc_number", models.PositiveIntegerField(null=True)),
                ("order_in_cluster", models.PositiveSmallIntegerField(default=1)),
                ("external_deadline", models.DateTimeField(null=True)),
                ("internal_goal", models.DateTimeField(null=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "cluster",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="rpc.cluster",
                    ),
                ),
                (
                    "disposition",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="rpc.disposition",
                    ),
                ),
                (
                    "draft",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="doc.document",
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "intended_boilerplate",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.tlpboilerplatechoicename",
                    ),
                ),
                (
                    "intended_std_level",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.stdlevelname",
                    ),
                ),
                (
                    "intended_stream",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.streamname",
                    ),
                ),
                (
                    "submitted_boilerplate",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.tlpboilerplatechoicename",
                    ),
                ),
                (
                    "submitted_format",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.sourceformatname",
                    ),
                ),
                (
                    "submitted_std_level",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.stdlevelname",
                    ),
                ),
                (
                    "submitted_stream",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="name.streamname",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical rfc to be",
                "verbose_name_plural": "historical rfc to bes",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="FinalApproval",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("requested", models.DateTimeField(default=django.utils.timezone.now)),
                ("approved", models.DateTimeField(null=True)),
                (
                    "approver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
                (
                    "rfc_to_be",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="rpc.rfctobe"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Assignment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("assigned", "assigned"),
                            ("in progress", "in progress"),
                            ("done", "done"),
                        ],
                        default="assigned",
                        max_length=32,
                    ),
                ),
                ("time_spent", models.DurationField(default=datetime.timedelta(0))),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="rpc.rpcperson"
                    ),
                ),
                (
                    "rfc_to_be",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="rpc.rfctobe"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ActionHolder",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("since_when", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed", models.DateTimeField(null=True)),
                ("comment", models.TextField(blank=True)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="person.person"
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="rpcrelateddocument",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("target_document__isnull", True),
                    ("target_rfctobe__isnull", True),
                    _connector="XOR",
                ),
                name="rpcrelateddocument_exactly_one_target",
                violation_error_message="exactly one target field must be set",
            ),
        ),
        migrations.AddConstraint(
            model_name="rpcdocumentcomment",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("document__isnull", True),
                    ("rfc_to_be__isnull", True),
                    _connector="XOR",
                ),
                name="rpcdocumentcomment_exactly_one_target",
                violation_error_message="exactly one of document or rfc_to_be must be set",
            ),
        ),
        migrations.AddConstraint(
            model_name="rfctobe",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("draft__isnull", False),
                    ("is_april_first_rfc", True),
                    _connector="XOR",
                ),
                name="rfctobe_draft_not_null_xor_is_april_first_rfc",
                violation_error_message="draft must be null if and only if is_april_first_rfc",
            ),
        ),
        migrations.AddConstraint(
            model_name="rfctobe",
            constraint=models.UniqueConstraint(
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                fields=("cluster", "order_in_cluster"),
                name="rfctobe_unique_order_in_cluster",
                violation_error_message="order in cluster must be unique",
            ),
        ),
    ]
