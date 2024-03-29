# Generated by Django 4.2.2 on 2023-06-14 19:47

from django.db import migrations
from django.db.models import OuterRef, Subquery
import django.db.models.deletion
import ietf.utils.models


def forward(apps, schema_editor):
    Nomination = apps.get_model('nomcom', 'Nomination')
    Person = apps.get_model("person", "Person")
    Nomination.objects.exclude(
        user__isnull=True
    ).update(
        person=Subquery(
            Person.objects.filter(user_id=OuterRef("user_id")).values("pk")[:1]
        )
    )

    Feedback = apps.get_model('nomcom', 'Feedback')
    Feedback.objects.exclude(
        user__isnull=True
    ).update(
        person=Subquery(
            Person.objects.filter(user_id=OuterRef("user_id")).values("pk")[:1]
        )
    )

def reverse(apps, schema_editor):
    Nomination = apps.get_model('nomcom', 'Nomination')
    Person = apps.get_model("person", "Person")
    Nomination.objects.exclude(
        person__isnull=True
    ).update(
        user_id=Subquery(
            Person.objects.filter(pk=OuterRef("person_id")).values("user_id")[:1]
        )
    )

    Feedback = apps.get_model('nomcom', 'Feedback')
    Feedback.objects.exclude(
        person__isnull=True
    ).update(
        user_id=Subquery(
            Person.objects.filter(pk=OuterRef("person_id")).values("user_id")[:1]
        )
    )

class Migration(migrations.Migration):
    dependencies = [
        ("person", "0001_initial"),
        ("nomcom", "0004_volunteer_origin_volunteer_time_volunteer_withdrawn"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedback",
            name="person",
            field=ietf.utils.models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="person.person",
            ),
        ),
        migrations.AddField(
            model_name="nomination",
            name="person",
            field=ietf.utils.models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="person.person",
            ),
        ),
        migrations.RunPython(forward, reverse),
        migrations.RemoveField(
            model_name="feedback",
            name="user",
            field=ietf.utils.models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="user.user",
            ),
        ),
        migrations.RemoveField(
            model_name="nomination",
            name="user",
            field=ietf.utils.models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="user.user",
            ),
        ),
    ]
