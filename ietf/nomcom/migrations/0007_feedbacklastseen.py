# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0004_auto_20150308_0440'),
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
    ]
