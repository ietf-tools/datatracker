# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations # pyflakes:ignore


def set_primary_email(apps, schema_editor):
    Person = apps.get_model("person", "Person")
    for person in Person.objects.all():
        email = person.email_set.order_by("-active","-time").first()
        if email:
            email.primary = True
            email.save()

def clear_primary_email(apps, schema_editor):
    Person = apps.get_model("person", "Person")
    for person in Person.objects.all():
        email_list = person.email_set.filter(primary=True)
        for email in email_list:
            email.primary = False
            email.save()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0002_email_primary'),
    ]

    operations = [
        migrations.RunPython(
            set_primary_email,
            clear_primary_email),
    ]
