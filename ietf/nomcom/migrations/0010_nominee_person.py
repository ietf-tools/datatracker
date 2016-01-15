# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

def populate_person(apps, schema_editor):
    Nominee = apps.get_model('nomcom','Nominee')
    for n in Nominee.objects.all():
        n.person = n.email.person
        n.save()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0004_auto_20150308_0440'),
        ('nomcom', '0009_remove_requirements_dbtemplate_type_from_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='nominee',
            name='person',
            field=models.ForeignKey(blank=True, to='person.Person', null=True),
            preserve_default=True,
        ),
        migrations.RunPython(populate_person,None)
    ]
