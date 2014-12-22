# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0001_initial'),
        ('group', '0001_initial'),
        ('name', '0001_initial'),
        ('contenttypes', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='group',
            field=models.ForeignKey(blank=True, to='group.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='intended_std_level',
            field=models.ForeignKey(verbose_name=b'Intended standardization level', blank=True, to='name.IntendedStdLevelName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='shepherd',
            field=models.ForeignKey(related_name='shepherd_document_set', blank=True, to='person.Email', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='states',
            field=models.ManyToManyField(to='doc.State', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='std_level',
            field=models.ForeignKey(verbose_name=b'Standardization level', blank=True, to='name.StdLevelName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='stream',
            field=models.ForeignKey(blank=True, to='name.StreamName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='tags',
            field=models.ManyToManyField(to='name.DocTagName', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='document',
            name='type',
            field=models.ForeignKey(blank=True, to='name.DocTypeName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='docreminder',
            name='event',
            field=models.ForeignKey(to='doc.DocEvent'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='docreminder',
            name='type',
            field=models.ForeignKey(to='name.DocReminderTypeName'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistoryauthor',
            name='author',
            field=models.ForeignKey(to='person.Email'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistoryauthor',
            name='document',
            field=models.ForeignKey(to='doc.DocHistory'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='ad',
            field=models.ForeignKey(related_name='ad_dochistory_set', verbose_name=b'area director', blank=True, to='person.Person', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='authors',
            field=models.ManyToManyField(to='person.Email', through='doc.DocHistoryAuthor', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='doc',
            field=models.ForeignKey(related_name='history_set', to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='group',
            field=models.ForeignKey(blank=True, to='group.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='intended_std_level',
            field=models.ForeignKey(verbose_name=b'Intended standardization level', blank=True, to='name.IntendedStdLevelName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='related',
            field=models.ManyToManyField(to='doc.DocAlias', through='doc.RelatedDocHistory', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='shepherd',
            field=models.ForeignKey(related_name='shepherd_dochistory_set', blank=True, to='person.Email', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='states',
            field=models.ManyToManyField(to='doc.State', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='std_level',
            field=models.ForeignKey(verbose_name=b'Standardization level', blank=True, to='name.StdLevelName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='stream',
            field=models.ForeignKey(blank=True, to='name.StreamName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='tags',
            field=models.ManyToManyField(to='name.DocTagName', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dochistory',
            name='type',
            field=models.ForeignKey(blank=True, to='name.DocTypeName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='docevent',
            name='by',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='docevent',
            name='doc',
            field=models.ForeignKey(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='docalias',
            name='document',
            field=models.ForeignKey(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deletedevent',
            name='by',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deletedevent',
            name='content_type',
            field=models.ForeignKey(to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballottype',
            name='doc_type',
            field=models.ForeignKey(blank=True, to='name.DocTypeName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballottype',
            name='positions',
            field=models.ManyToManyField(to='name.BallotPositionName', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballotpositiondocevent',
            name='ad',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballotpositiondocevent',
            name='ballot',
            field=models.ForeignKey(default=None, to='doc.BallotDocEvent', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballotpositiondocevent',
            name='pos',
            field=models.ForeignKey(default=b'norecord', verbose_name=b'position', to='name.BallotPositionName'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ballotdocevent',
            name='ballot_type',
            field=models.ForeignKey(to='doc.BallotType'),
            preserve_default=True,
        ),
    ]
