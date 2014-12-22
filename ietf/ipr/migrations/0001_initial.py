# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message', '__first__'),
        ('name', '0001_initial'),
        ('doc', '0002_auto_20141222_1749'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IprContact',
            fields=[
                ('contact_id', models.AutoField(serialize=False, primary_key=True)),
                ('contact_type', models.IntegerField(choices=[(1, b'Patent Holder Contact'), (2, b'IETF Participant Contact'), (3, b'Submitter Contact')])),
                ('name', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255, blank=True)),
                ('department', models.CharField(max_length=255, blank=True)),
                ('address1', models.CharField(max_length=255, blank=True)),
                ('address2', models.CharField(max_length=255, blank=True)),
                ('telephone', models.CharField(max_length=25, blank=True)),
                ('fax', models.CharField(max_length=25, blank=True)),
                ('email', models.EmailField(max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprDetail',
            fields=[
                ('ipr_id', models.AutoField(serialize=False, primary_key=True)),
                ('title', models.CharField(max_length=255, db_column=b'document_title', blank=True)),
                ('legacy_url_0', models.CharField(max_length=255, null=True, db_column=b'old_ipr_url', blank=True)),
                ('legacy_url_1', models.CharField(max_length=255, null=True, db_column=b'additional_old_url1', blank=True)),
                ('legacy_title_1', models.CharField(max_length=255, null=True, db_column=b'additional_old_title1', blank=True)),
                ('legacy_url_2', models.CharField(max_length=255, null=True, db_column=b'additional_old_url2', blank=True)),
                ('legacy_title_2', models.CharField(max_length=255, null=True, db_column=b'additional_old_title2', blank=True)),
                ('legal_name', models.CharField(max_length=255, verbose_name=b'Legal Name', db_column=b'p_h_legal_name')),
                ('rfc_number', models.IntegerField(null=True, editable=False, blank=True)),
                ('id_document_tag', models.IntegerField(null=True, editable=False, blank=True)),
                ('other_designations', models.CharField(max_length=255, blank=True)),
                ('document_sections', models.TextField(max_length=255, verbose_name=b'Specific document sections covered', db_column=b'disclouser_identify', blank=True)),
                ('patents', models.TextField(max_length=255, verbose_name=b'Patent Applications', db_column=b'p_applications')),
                ('date_applied', models.CharField(max_length=255)),
                ('country', models.CharField(max_length=255)),
                ('notes', models.TextField(verbose_name=b'Additional notes', db_column=b'p_notes', blank=True)),
                ('is_pending', models.IntegerField(blank=True, null=True, verbose_name=b'Unpublished Pending Patent Application', db_column=b'selecttype', choices=[(0, b'NO'), (1, b'YES'), (2, b'NO')])),
                ('applies_to_all', models.IntegerField(blank=True, null=True, verbose_name=b'Applies to all IPR owned by Submitter', db_column=b'selectowned', choices=[(0, b'NO'), (1, b'YES'), (2, b'NO')])),
                ('licensing_option', models.IntegerField(blank=True, null=True, choices=[(0, b''), (1, b'a) No License Required for Implementers.'), (2, b'b) Royalty-Free, Reasonable and Non-Discriminatory License to All Implementers.'), (3, b'c) Reasonable and Non-Discriminatory License to All Implementers with Possible Royalty/Fee.'), (4, b'd) Licensing Declaration to be Provided Later (implies a willingness to commit to the provisions of a), b), or c) above to all implementers; otherwise, the next option "Unwilling to Commit to the Provisions of a), b), or c) Above". - must be selected).'), (5, b'e) Unwilling to Commit to the Provisions of a), b), or c) Above.'), (6, b'f) See Text Below for Licensing Declaration.')])),
                ('lic_opt_a_sub', models.IntegerField(null=True, editable=False, choices=[(0, b''), (1, b'The licensing declaration is limited solely to standards-track IETF documents.')])),
                ('lic_opt_b_sub', models.IntegerField(null=True, editable=False, choices=[(0, b''), (1, b'The licensing declaration is limited solely to standards-track IETF documents.')])),
                ('lic_opt_c_sub', models.IntegerField(null=True, editable=False, choices=[(0, b''), (1, b'The licensing declaration is limited solely to standards-track IETF documents.')])),
                ('comments', models.TextField(verbose_name=b'Licensing Comments', blank=True)),
                ('lic_checkbox', models.BooleanField(default=False, verbose_name=b'All terms and conditions has been disclosed')),
                ('other_notes', models.TextField(blank=True)),
                ('third_party', models.BooleanField(default=False)),
                ('generic', models.BooleanField(default=False)),
                ('comply', models.BooleanField(default=False)),
                ('status', models.IntegerField(blank=True, null=True, choices=[(0, b'Waiting for approval'), (1, b'Approved and Posted'), (2, b'Rejected by Administrator'), (3, b'Removed by Request')])),
                ('submitted_date', models.DateField(blank=True)),
                ('update_notified_date', models.DateField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprDisclosureBase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('compliant', models.BooleanField(default=True)),
                ('holder_legal_name', models.CharField(max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('other_designations', models.CharField(max_length=255, blank=True)),
                ('submitter_name', models.CharField(max_length=255)),
                ('submitter_email', models.EmailField(max_length=75)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('title', models.CharField(max_length=255, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HolderIprDisclosure',
            fields=[
                ('iprdisclosurebase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ipr.IprDisclosureBase')),
                ('ietfer_name', models.CharField(max_length=255, blank=True)),
                ('ietfer_contact_email', models.EmailField(max_length=75, blank=True)),
                ('ietfer_contact_info', models.TextField(blank=True)),
                ('patent_info', models.TextField()),
                ('has_patent_pending', models.BooleanField(default=False)),
                ('holder_contact_email', models.EmailField(max_length=75)),
                ('holder_contact_name', models.CharField(max_length=255)),
                ('holder_contact_info', models.TextField(blank=True)),
                ('licensing_comments', models.TextField(blank=True)),
                ('submitter_claims_all_terms_disclosed', models.BooleanField(default=False)),
                ('licensing', models.ForeignKey(to='name.IprLicenseTypeName')),
            ],
            options={
            },
            bases=('ipr.iprdisclosurebase',),
        ),
        migrations.CreateModel(
            name='GenericIprDisclosure',
            fields=[
                ('iprdisclosurebase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ipr.IprDisclosureBase')),
                ('holder_contact_name', models.CharField(max_length=255)),
                ('holder_contact_email', models.EmailField(max_length=75)),
                ('holder_contact_info', models.TextField(blank=True)),
                ('statement', models.TextField()),
            ],
            options={
            },
            bases=('ipr.iprdisclosurebase',),
        ),
        migrations.CreateModel(
            name='IprDocAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rev', models.CharField(max_length=2, blank=True)),
                ('doc_alias', models.ForeignKey(to='doc.DocAlias')),
                ('ipr', models.ForeignKey(to='ipr.IprDetail')),
            ],
            options={
                'verbose_name': 'IPR document alias',
                'verbose_name_plural': 'IPR document aliases',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprDocRel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sections', models.TextField(blank=True)),
                ('revisions', models.CharField(max_length=16, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('desc', models.TextField()),
                ('response_due', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'ordering': ['-time', '-id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('notification', models.TextField(blank=True)),
                ('date_sent', models.DateField(null=True, blank=True)),
                ('time_sent', models.CharField(max_length=25, blank=True)),
                ('ipr', models.ForeignKey(to='ipr.IprDetail')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IprUpdate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status_to_be', models.IntegerField(null=True, blank=True)),
                ('processed', models.IntegerField(null=True, blank=True)),
                ('ipr', models.ForeignKey(related_name='updates', to='ipr.IprDetail')),
                ('updated', models.ForeignKey(related_name='updated_by', db_column=b'updated', to='ipr.IprDetail')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LegacyMigrationIprEvent',
            fields=[
                ('iprevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ipr.IprEvent')),
            ],
            options={
            },
            bases=('ipr.iprevent',),
        ),
        migrations.CreateModel(
            name='NonDocSpecificIprDisclosure',
            fields=[
                ('iprdisclosurebase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ipr.IprDisclosureBase')),
                ('holder_contact_name', models.CharField(max_length=255)),
                ('holder_contact_email', models.EmailField(max_length=75)),
                ('holder_contact_info', models.TextField(blank=True)),
                ('patent_info', models.TextField()),
                ('has_patent_pending', models.BooleanField(default=False)),
                ('statement', models.TextField()),
            ],
            options={
            },
            bases=('ipr.iprdisclosurebase',),
        ),
        migrations.CreateModel(
            name='RelatedIpr',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('relationship', models.ForeignKey(to='name.DocRelationshipName')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ThirdPartyIprDisclosure',
            fields=[
                ('iprdisclosurebase_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ipr.IprDisclosureBase')),
                ('ietfer_name', models.CharField(max_length=255)),
                ('ietfer_contact_email', models.EmailField(max_length=75)),
                ('ietfer_contact_info', models.TextField(blank=True)),
                ('patent_info', models.TextField()),
                ('has_patent_pending', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=('ipr.iprdisclosurebase',),
        ),
        migrations.AddField(
            model_name='relatedipr',
            name='source',
            field=models.ForeignKey(related_name='relatedipr_source_set', to='ipr.IprDisclosureBase'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='relatedipr',
            name='target',
            field=models.ForeignKey(related_name='relatedipr_target_set', to='ipr.IprDisclosureBase'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprevent',
            name='by',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprevent',
            name='disclosure',
            field=models.ForeignKey(to='ipr.IprDisclosureBase'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprevent',
            name='in_reply_to',
            field=models.ForeignKey(related_name='irtoevents', blank=True, to='message.Message', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprevent',
            name='message',
            field=models.ForeignKey(related_name='msgevents', blank=True, to='message.Message', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprevent',
            name='type',
            field=models.ForeignKey(to='name.IprEventTypeName'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdocrel',
            name='disclosure',
            field=models.ForeignKey(to='ipr.IprDisclosureBase'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdocrel',
            name='document',
            field=models.ForeignKey(to='doc.DocAlias'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdisclosurebase',
            name='by',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdisclosurebase',
            name='docs',
            field=models.ManyToManyField(to='doc.DocAlias', through='ipr.IprDocRel'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdisclosurebase',
            name='rel',
            field=models.ManyToManyField(to='ipr.IprDisclosureBase', through='ipr.RelatedIpr'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprdisclosurebase',
            name='state',
            field=models.ForeignKey(to='name.IprDisclosureStateName'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iprcontact',
            name='ipr',
            field=models.ForeignKey(related_name='contact', to='ipr.IprDetail'),
            preserve_default=True,
        ),
    ]
