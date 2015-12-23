# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime

from django.db import models, migrations

def create_lastseen(apps, schema_editor):
    NomCom = apps.get_model('nomcom','NomCom')
    FeedbackLastSeen = apps.get_model('nomcom','FeedbackLastSeen')
    now = datetime.datetime.now()
    for nc in NomCom.objects.all():
        reviewers = [r.person for r in nc.group.role_set.all()]
        nominees = nc.nominee_set.all()
        for r in reviewers:
            for n in nominees:
                FeedbackLastSeen.objects.create(reviewer=r,nominee=n,time=now)
        
def remove_lastseen(apps, schema_editor):
    FeedbackLastSeen = apps.get_model('nomcom','FeedbackLastSeen')
    FeedbackLastSeen.objects.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0004_auto_20150308_0440'),
        ('group',  '0006_auto_20150718_0509'),
        ('nomcom', '0006_improve_default_questionnaire_templates'),
    ]

    operations = [

        migrations.CreateModel(
            name='FeedbackLastSeen',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(auto_now=True)),
                ('nominee', models.ForeignKey(to='nomcom.Nominee')),
                ('reviewer', models.ForeignKey(to='person.Person')),
            ],
            options={
            },
            bases=(models.Model,),
        ),

       migrations.RunPython(create_lastseen,remove_lastseen)

    ]
