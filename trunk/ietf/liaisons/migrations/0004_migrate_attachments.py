# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

# This migration handles converting a standard Many-to-Many field to one
# with a through table

def copy_attachments(apps, schema_editor):
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    LiaisonStatementAttachment = apps.get_model("liaisons", "LiaisonStatementAttachment")
    for liaison in LiaisonStatement.objects.all():
        for doc in liaison.attachments.all():
            LiaisonStatementAttachment.objects.create(
                statement=liaison,
                document=doc,
                removed=False)

class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0003_migrate_general'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiaisonStatementAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('removed', models.BooleanField(default=False)),
                ('document', models.ForeignKey(to='doc.Document')),
                ('statement', models.ForeignKey(to='liaisons.LiaisonStatement')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(copy_attachments),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='attachments',
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='attachments',
            field=models.ManyToManyField(to='doc.Document', through='liaisons.LiaisonStatementAttachment', blank=True),
            preserve_default=True,
        ),
    ]
