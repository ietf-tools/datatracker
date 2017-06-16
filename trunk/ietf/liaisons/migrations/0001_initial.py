# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0002_auto_20141222_1749'),
        ('person', '0001_initial'),
        ('name', '0007_populate_liaison_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiaisonStatement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=255, blank=True)),
                ('body', models.TextField(blank=True)),
                ('deadline', models.DateField(null=True, blank=True)),
                ('from_name', models.CharField(help_text=b'Name of the sender body', max_length=255)),
                ('to_name', models.CharField(help_text=b'Name of the recipient body', max_length=255)),
                ('to_contact', models.CharField(help_text=b'Contacts at recipient body', max_length=255, blank=True)),
                ('reply_to', models.CharField(max_length=255, blank=True)),
                ('response_contact', models.CharField(max_length=255, blank=True)),
                ('technical_contact', models.CharField(max_length=255, blank=True)),
                ('cc', models.TextField(blank=True)),
                ('submitted', models.DateTimeField(null=True, blank=True)),
                ('modified', models.DateTimeField(null=True, blank=True)),
                ('approved', models.DateTimeField(null=True, blank=True)),
                ('action_taken', models.BooleanField(default=False)),
                ('attachments', models.ManyToManyField(to='doc.Document', blank=True)),
                ('from_contact', models.ForeignKey(blank=True, to='person.Email', null=True)),
                ('from_group', models.ForeignKey(related_name='liaisonstatement_from_set', blank=True, to='group.Group', help_text=b'Sender group, if it exists', null=True)),
                ('purpose', models.ForeignKey(to='name.LiaisonStatementPurposeName')),
                ('related_to', models.ForeignKey(blank=True, to='liaisons.LiaisonStatement', null=True)),
                ('to_group', models.ForeignKey(related_name='liaisonstatement_to_set', blank=True, to='group.Group', help_text=b'Recipient group, if it exists', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
