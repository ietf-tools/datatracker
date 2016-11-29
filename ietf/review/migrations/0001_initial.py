# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0015_insert_review_name_data'),
        ('group', '0008_auto_20160505_0523'),
        ('person', '0014_auto_20160613_0751'),
        ('doc', '0012_auto_20160207_0537'),
    ]

    operations = [
        migrations.CreateModel(
            name='NextReviewerInTeam',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('next_reviewer', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name': 'next reviewer in team setting',
                'verbose_name_plural': 'next reviewer in team settings',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ResultUsedInReviewTeam',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('result', models.ForeignKey(to='name.ReviewResultName')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name': 'review result used in team setting',
                'verbose_name_plural': 'review result used in team settings',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewerSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('min_interval', models.IntegerField(default=30, verbose_name=b'Can review at most', choices=[(7, b'Once per week'), (14, b'Once per fortnight'), (30, b'Once per month'), (61, b'Once per two months'), (91, b'Once per quarter')])),
                ('filter_re', models.CharField(help_text=b'Draft names matching regular expression should not be assigned', max_length=255, verbose_name=b'Filter regexp', blank=True)),
                ('skip_next', models.IntegerField(default=0, verbose_name=b'Skip next assignments')),
                ('remind_days_before_deadline', models.IntegerField(help_text=b"To get an email reminder in case you forget to do an assigned review, enter the number of days before a review deadline you want to receive it. Clear the field if you don't want a reminder.", null=True, blank=True)),
                ('person', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name_plural': 'reviewer settings',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('old_id', models.IntegerField(help_text=b'ID in previous review system', null=True, blank=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('deadline', models.DateField()),
                ('requested_rev', models.CharField(help_text=b'Fill in if a specific revision is to be reviewed, e.g. 02', max_length=16, verbose_name=b'requested revision', blank=True)),
                ('reviewed_rev', models.CharField(max_length=16, verbose_name=b'reviewed revision', blank=True)),
                ('doc', models.ForeignKey(related_name='reviewrequest_set', to='doc.Document')),
                ('requested_by', models.ForeignKey(to='person.Person')),
                ('result', models.ForeignKey(blank=True, to='name.ReviewResultName', null=True)),
                ('review', models.OneToOneField(null=True, blank=True, to='doc.Document')),
                ('reviewer', models.ForeignKey(blank=True, to='person.Email', null=True)),
                ('state', models.ForeignKey(to='name.ReviewRequestStateName')),
                ('team', models.ForeignKey(to='group.Group')),
                ('type', models.ForeignKey(to='name.ReviewTypeName')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewWish',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('doc', models.ForeignKey(to='doc.Document')),
                ('person', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name_plural': 'review wishes',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TypeUsedInReviewTeam',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('team', models.ForeignKey(to='group.Group')),
                ('type', models.ForeignKey(to='name.ReviewTypeName')),
            ],
            options={
                'verbose_name': 'review type used in team setting',
                'verbose_name_plural': 'review type used in team settings',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UnavailablePeriod',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.DateField(default=datetime.date.today, help_text=b"Choose the start date so that you can still do a review if it's assigned just before the start date - this usually means you should mark yourself unavailable for assignment some time before you are actually away.")),
                ('end_date', models.DateField(help_text=b'Leaving the end date blank means that the period continues indefinitely. You can end it later.', null=True, blank=True)),
                ('availability', models.CharField(max_length=30, choices=[(b'canfinish', b'Can do follow-ups'), (b'unavailable', b'Completely unavailable')])),
                ('person', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
