# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0008_auto_20160505_0523'),
        ('name', '0012_insert_review_name_data'),
        ('doc', '0012_auto_20160207_0537'),
        ('person', '0006_auto_20160503_0937'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reviewer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('frequency', models.IntegerField(default=30, help_text=b'Can review every N days')),
                ('unavailable_until', models.DateTimeField(help_text=b'When will this reviewer be available again', null=True, blank=True)),
                ('filter_re', models.CharField(max_length=255, blank=True)),
                ('skip_next', models.IntegerField(help_text=b'Skip the next N review assignments')),
                ('person', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('deadline', models.DateTimeField()),
                ('requested_rev', models.CharField(help_text=b'Fill in if a specific revision is to be reviewed, e.g. 02', max_length=16, verbose_name=b'requested revision', blank=True)),
                ('reviewed_rev', models.CharField(max_length=16, verbose_name=b'reviewed revision', blank=True)),
                ('doc', models.ForeignKey(related_name='review_request_set', to='doc.Document')),
                ('result', models.ForeignKey(blank=True, to='name.ReviewResultName', null=True)),
                ('review', models.OneToOneField(null=True, blank=True, to='doc.Document')),
                ('reviewer', models.ForeignKey(blank=True, to='group.Role', null=True)),
                ('state', models.ForeignKey(to='name.ReviewRequestStateName')),
                ('team', models.ForeignKey(to='group.Group')),
                ('type', models.ForeignKey(to='name.ReviewTypeName')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
