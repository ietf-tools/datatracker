# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0001_initial'),
        ('person', '0001_initial'),
        ('doc', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('name', models.CharField(max_length=80)),
                ('description', models.TextField(blank=True)),
                ('list_email', models.CharField(max_length=64, blank=True)),
                ('list_subscribe', models.CharField(max_length=255, blank=True)),
                ('list_archive', models.CharField(max_length=255, blank=True)),
                ('comments', models.TextField(blank=True)),
                ('acronym', models.SlugField(unique=True, max_length=40)),
                ('ad', models.ForeignKey(verbose_name=b'AD', blank=True, to='person.Person', null=True)),
                ('charter', models.OneToOneField(related_name='chartered_group', null=True, blank=True, to='doc.Document')),
                ('parent', models.ForeignKey(blank=True, to='group.Group', null=True)),
                ('state', models.ForeignKey(to='name.GroupStateName', null=True)),
                ('type', models.ForeignKey(to='name.GroupTypeName', null=True)),
                ('unused_states', models.ManyToManyField(help_text=b'Document states that have been disabled for the group', to='doc.State', blank=True)),
                ('unused_tags', models.ManyToManyField(help_text=b'Document tags that have been disabled for the group', to='name.DocTagName', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now, help_text=b'When the event happened')),
                ('type', models.CharField(max_length=50, choices=[(b'changed_state', b'Changed state'), (b'added_comment', b'Added comment'), (b'info_changed', b'Changed metadata'), (b'requested_close', b'Requested closing group'), (b'changed_milestone', b'Changed milestone'), (b'sent_notification', b'Sent notification')])),
                ('desc', models.TextField()),
            ],
            options={
                'ordering': ['-time', 'id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChangeStateGroupEvent',
            fields=[
                ('groupevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='group.GroupEvent')),
                ('state', models.ForeignKey(to='name.GroupStateName')),
            ],
            options={
            },
            bases=('group.groupevent',),
        ),
        migrations.CreateModel(
            name='GroupHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('name', models.CharField(max_length=80)),
                ('description', models.TextField(blank=True)),
                ('list_email', models.CharField(max_length=64, blank=True)),
                ('list_subscribe', models.CharField(max_length=255, blank=True)),
                ('list_archive', models.CharField(max_length=255, blank=True)),
                ('comments', models.TextField(blank=True)),
                ('acronym', models.CharField(max_length=40)),
                ('ad', models.ForeignKey(verbose_name=b'AD', blank=True, to='person.Person', null=True)),
                ('group', models.ForeignKey(related_name='history_set', to='group.Group')),
                ('parent', models.ForeignKey(blank=True, to='group.Group', null=True)),
                ('state', models.ForeignKey(to='name.GroupStateName', null=True)),
                ('type', models.ForeignKey(to='name.GroupTypeName', null=True)),
                ('unused_states', models.ManyToManyField(help_text=b'Document states that have been disabled for the group', to='doc.State', blank=True)),
                ('unused_tags', models.ManyToManyField(help_text=b'Document tags that have been disabled for the group', to='name.DocTagName', blank=True)),
            ],
            options={
                'verbose_name_plural': 'group histories',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupMilestone',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('desc', models.CharField(max_length=500, verbose_name=b'Description')),
                ('due', models.DateField()),
                ('resolved', models.CharField(help_text=b'Explanation of why milestone is resolved (usually "Done"), or empty if still due', max_length=50, blank=True)),
                ('time', models.DateTimeField(auto_now=True)),
                ('docs', models.ManyToManyField(to='doc.Document', blank=True)),
                ('group', models.ForeignKey(to='group.Group')),
                ('state', models.ForeignKey(to='name.GroupMilestoneStateName')),
            ],
            options={
                'ordering': ['due', 'id'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupMilestoneHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('desc', models.CharField(max_length=500, verbose_name=b'Description')),
                ('due', models.DateField()),
                ('resolved', models.CharField(help_text=b'Explanation of why milestone is resolved (usually "Done"), or empty if still due', max_length=50, blank=True)),
                ('time', models.DateTimeField()),
                ('docs', models.ManyToManyField(to='doc.Document', blank=True)),
                ('group', models.ForeignKey(to='group.Group')),
                ('milestone', models.ForeignKey(related_name='history_set', to='group.GroupMilestone')),
                ('state', models.ForeignKey(to='name.GroupMilestoneStateName')),
            ],
            options={
                'ordering': ['due', 'id'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupStateTransitions',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('group', models.ForeignKey(to='group.Group')),
                ('next_states', models.ManyToManyField(related_name='previous_groupstatetransitions_states', to='doc.State')),
                ('state', models.ForeignKey(help_text=b'State for which the next states should be overridden', to='doc.State')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupURL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('url', models.URLField()),
                ('group', models.ForeignKey(to='group.Group')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MilestoneGroupEvent',
            fields=[
                ('groupevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='group.GroupEvent')),
                ('milestone', models.ForeignKey(to='group.GroupMilestone')),
            ],
            options={
            },
            bases=('group.groupevent',),
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.ForeignKey(help_text=b'Email address used by person for this role', to='person.Email')),
                ('group', models.ForeignKey(to='group.Group')),
                ('name', models.ForeignKey(to='name.RoleName')),
                ('person', models.ForeignKey(to='person.Person')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RoleHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.ForeignKey(help_text=b'Email address used by person for this role', to='person.Email')),
                ('group', models.ForeignKey(to='group.GroupHistory')),
                ('name', models.ForeignKey(to='name.RoleName')),
                ('person', models.ForeignKey(to='person.Person')),
            ],
            options={
                'verbose_name_plural': 'role histories',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='groupevent',
            name='by',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='groupevent',
            name='group',
            field=models.ForeignKey(to='group.Group'),
            preserve_default=True,
        ),
    ]
