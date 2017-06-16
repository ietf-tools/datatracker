# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0003_auto_20150304_0743'),
        ('person', '0001_initial'),
        ('doc', '0002_auto_20141222_1749'),
        ('name', '0007_populate_liaison_names'),
        ('liaisons', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiaisonStatementEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('desc', models.TextField()),
                ('by', models.ForeignKey(to='person.Person')),
                ('statement', models.ForeignKey(to='liaisons.LiaisonStatement')),
                ('type', models.ForeignKey(to='name.LiaisonStatementEventTypeName')),
            ],
            options={'ordering': ['-time', '-id']},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LiaisonStatementGroupContacts',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('contacts', models.CharField(max_length=255,blank=True)),
                ('cc_contacts', models.CharField(max_length=255,blank=True)),
                ('group', models.ForeignKey(to='group.Group', unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RelatedLiaisonStatement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('relationship', models.ForeignKey(to='name.DocRelationshipName')),
                ('source', models.ForeignKey(related_name='source_of_set', to='liaisons.LiaisonStatement')),
                ('target', models.ForeignKey(related_name='target_of_set', to='liaisons.LiaisonStatement')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RenameField(
            model_name='liaisonstatement',
            old_name='cc',
            new_name='cc_contacts',
        ),
        migrations.RenameField(
            model_name='liaisonstatement',
            old_name='to_contact',
            new_name='to_contacts',
        ),
        migrations.RenameField(
            model_name='liaisonstatement',
            old_name='technical_contact',
            new_name='technical_contacts',
        ),
        migrations.RenameField(
            model_name='liaisonstatement',
            old_name='response_contact',
            new_name='response_contacts',
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='action_holder_contacts',
            field=models.CharField(help_text=b'Who makes sure action is completed', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='from_groups',
            field=models.ManyToManyField(related_name='liaisonsatement_from_set', to='group.Group', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='other_identifiers',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='state',
            field=models.ForeignKey(default=b'pending', to='name.LiaisonStatementState'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='tags',
            field=models.ManyToManyField(to='name.LiaisonStatementTagName', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='liaisonstatement',
            name='to_groups',
            field=models.ManyToManyField(related_name='liaisonsatement_to_set', to='group.Group', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='liaisonstatement',
            name='response_contacts',
            field=models.CharField(help_text=b'Where to send a response', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='liaisonstatement',
            name='technical_contacts',
            field=models.CharField(help_text=b'Who to contact for clarification', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
