# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BallotType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('slug', models.SlugField()),
                ('name', models.CharField(max_length=255)),
                ('question', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeletedEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('json', models.TextField(help_text=b'Deleted object in JSON format, with attribute names chosen to be suitable for passing into the relevant create method.')),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
            ],
            options={
                'verbose_name': 'document alias',
                'verbose_name_plural': 'document aliases',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now, help_text=b'When the event happened', db_index=True)),
                ('type', models.CharField(max_length=50, choices=[(b'new_revision', b'Added new revision'), (b'changed_document', b'Changed document metadata'), (b'added_comment', b'Added comment'), (b'deleted', b'Deleted document'), (b'changed_state', b'Changed state'), (b'changed_stream', b'Changed document stream'), (b'expired_document', b'Expired document'), (b'extended_expiry', b'Extended expiry of document'), (b'requested_resurrect', b'Requested resurrect'), (b'completed_resurrect', b'Completed resurrect'), (b'changed_consensus', b'Changed consensus'), (b'published_rfc', b'Published RFC'), (b'changed_group', b'Changed group'), (b'changed_protocol_writeup', b'Changed protocol writeup'), (b'changed_charter_milestone', b'Changed charter milestone'), (b'initial_review', b'Set initial review time'), (b'changed_review_announcement', b'Changed WG Review text'), (b'changed_action_announcement', b'Changed WG Action text'), (b'started_iesg_process', b'Started IESG process on document'), (b'created_ballot', b'Created ballot'), (b'closed_ballot', b'Closed ballot'), (b'sent_ballot_announcement', b'Sent ballot announcement'), (b'changed_ballot_position', b'Changed ballot position'), (b'changed_ballot_approval_text', b'Changed ballot approval text'), (b'changed_ballot_writeup_text', b'Changed ballot writeup text'), (b'changed_last_call_text', b'Changed last call text'), (b'requested_last_call', b'Requested last call'), (b'sent_last_call', b'Sent last call'), (b'scheduled_for_telechat', b'Scheduled for telechat'), (b'iesg_approved', b'IESG approved document (no problem)'), (b'iesg_disapproved', b'IESG disapproved document (do not publish)'), (b'approved_in_minute', b'Approved in minute'), (b'iana_review', b'IANA review comment'), (b'rfc_in_iana_registry', b'RFC is in IANA registry'), (b'rfc_editor_received_announcement', b'Announcement was received by RFC Editor'), (b'requested_publication', b'Publication at RFC Editor requested')])),
                ('desc', models.TextField()),
            ],
            options={
                'ordering': ['-time', '-id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ConsensusDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('consensus', models.NullBooleanField(default=None)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='BallotPositionDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('discuss', models.TextField(help_text=b'Discuss text if position is discuss', blank=True)),
                ('discuss_time', models.DateTimeField(help_text=b'Time discuss text was written', null=True, blank=True)),
                ('comment', models.TextField(help_text=b'Optional comment', blank=True)),
                ('comment_time', models.DateTimeField(help_text=b'Time optional comment was written', null=True, blank=True)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='BallotDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='DocHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('title', models.CharField(max_length=255)),
                ('abstract', models.TextField(blank=True)),
                ('rev', models.CharField(max_length=16, verbose_name=b'revision', blank=True)),
                ('pages', models.IntegerField(null=True, blank=True)),
                ('order', models.IntegerField(default=1, blank=True)),
                ('expires', models.DateTimeField(null=True, blank=True)),
                ('notify', models.CharField(max_length=255, blank=True)),
                ('external_url', models.URLField(blank=True)),
                ('note', models.TextField(blank=True)),
                ('internal_comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'document history',
                'verbose_name_plural': 'document histories',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocHistoryAuthor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('order', models.IntegerField()),
            ],
            options={
                'ordering': ['document', 'order'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocReminder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('due', models.DateTimeField()),
                ('active', models.BooleanField(default=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('title', models.CharField(max_length=255)),
                ('abstract', models.TextField(blank=True)),
                ('rev', models.CharField(max_length=16, verbose_name=b'revision', blank=True)),
                ('pages', models.IntegerField(null=True, blank=True)),
                ('order', models.IntegerField(default=1, blank=True)),
                ('expires', models.DateTimeField(null=True, blank=True)),
                ('notify', models.CharField(max_length=255, blank=True)),
                ('external_url', models.URLField(blank=True)),
                ('note', models.TextField(blank=True)),
                ('internal_comments', models.TextField(blank=True)),
                ('name', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('ad', models.ForeignKey(related_name='ad_document_set', verbose_name=b'area director', blank=True, to='person.Person', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocumentAuthor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('order', models.IntegerField(default=1)),
                ('author', models.ForeignKey(help_text=b'Email address used by author for submission', to='person.Email')),
                ('document', models.ForeignKey(to='doc.Document')),
            ],
            options={
                'ordering': ['document', 'order'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InitialReviewDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('expires', models.DateTimeField(null=True, blank=True)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='LastCallDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('expires', models.DateTimeField(null=True, blank=True)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='NewRevisionDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('rev', models.CharField(max_length=16)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='RelatedDocHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('relationship', models.ForeignKey(to='name.DocRelationshipName')),
                ('source', models.ForeignKey(to='doc.DocHistory')),
                ('target', models.ForeignKey(related_name='reversely_related_document_history_set', to='doc.DocAlias')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RelatedDocument',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('relationship', models.ForeignKey(to='name.DocRelationshipName')),
                ('source', models.ForeignKey(to='doc.Document')),
                ('target', models.ForeignKey(to='doc.DocAlias')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('slug', models.SlugField()),
                ('name', models.CharField(max_length=255)),
                ('used', models.BooleanField(default=True)),
                ('desc', models.TextField(blank=True)),
                ('order', models.IntegerField(default=0)),
                ('next_states', models.ManyToManyField(related_name='previous_states', to='doc.State', blank=True)),
            ],
            options={
                'ordering': ['type', 'order'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StateDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('state', models.ForeignKey(blank=True, to='doc.State', null=True)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='StateType',
            fields=[
                ('slug', models.CharField(max_length=30, serialize=False, primary_key=True)),
                ('label', models.CharField(help_text=b'Label that should be used (e.g. in admin) for state drop-down for this type of state', max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TelechatDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('telechat_date', models.DateField(null=True, blank=True)),
                ('returning_item', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.CreateModel(
            name='WriteupDocEvent',
            fields=[
                ('docevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='doc.DocEvent')),
                ('text', models.TextField(blank=True)),
            ],
            options={
            },
            bases=('doc.docevent',),
        ),
        migrations.AddField(
            model_name='statedocevent',
            name='state_type',
            field=models.ForeignKey(to='doc.StateType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='state',
            name='type',
            field=models.ForeignKey(to='doc.StateType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='authors',
            field=models.ManyToManyField(to='person.Email', through='doc.DocumentAuthor', blank=True),
            preserve_default=True,
        ),
    ]
