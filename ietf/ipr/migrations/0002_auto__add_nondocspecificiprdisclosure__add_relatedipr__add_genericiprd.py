# -*- coding: utf-8 -*-
from south.db import db
from south.v2 import SchemaMigration

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'NonDocSpecificIprDisclosure'
        db.create_table(u'ipr_nondocspecificiprdisclosure', (
            (u'iprdisclosurebase_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ipr.IprDisclosureBase'], unique=True, primary_key=True)),
            ('holder_contact_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('holder_contact_email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('holder_contact_info', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('patent_info', self.gf('django.db.models.fields.TextField')()),
            ('has_patent_pending', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('statement', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'ipr', ['NonDocSpecificIprDisclosure'])

        # Adding model 'RelatedIpr'
        db.create_table(u'ipr_relatedipr', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='relatedipr_source_set', to=orm['ipr.IprDisclosureBase'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='relatedipr_target_set', to=orm['ipr.IprDisclosureBase'])),
            ('relationship', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.DocRelationshipName'])),
        ))
        db.send_create_signal(u'ipr', ['RelatedIpr'])

        # Adding model 'GenericIprDisclosure'
        db.create_table(u'ipr_genericiprdisclosure', (
            (u'iprdisclosurebase_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ipr.IprDisclosureBase'], unique=True, primary_key=True)),
            ('holder_contact_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('holder_contact_email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('holder_contact_info', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('statement', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'ipr', ['GenericIprDisclosure'])

        # Adding model 'LegacyMigrationIprEvent'
        db.create_table(u'ipr_legacymigrationiprevent', (
            (u'iprevent_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ipr.IprEvent'], unique=True, primary_key=True)),
        ))
        db.send_create_signal(u'ipr', ['LegacyMigrationIprEvent'])

        # Adding model 'HolderIprDisclosure'
        db.create_table(u'ipr_holderiprdisclosure', (
            (u'iprdisclosurebase_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ipr.IprDisclosureBase'], unique=True, primary_key=True)),
            ('ietfer_name', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('ietfer_contact_email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('ietfer_contact_info', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('patent_info', self.gf('django.db.models.fields.TextField')()),
            ('has_patent_pending', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('holder_contact_email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('holder_contact_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('holder_contact_info', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('licensing', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.IprLicenseTypeName'])),
            ('licensing_comments', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('submitter_claims_all_terms_disclosed', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'ipr', ['HolderIprDisclosure'])

        # Adding model 'IprDisclosureBase'
        db.create_table(u'ipr_iprdisclosurebase', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Person'])),
            ('compliant', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('holder_legal_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('other_designations', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('state', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.IprDisclosureStateName'])),
            ('submitter_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('submitter_email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
        ))
        db.send_create_signal(u'ipr', ['IprDisclosureBase'])

        # Adding model 'IprEvent'
        db.create_table(u'ipr_iprevent', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['name.IprEventTypeName'])),
            ('by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['person.Person'])),
            ('disclosure', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ipr.IprDisclosureBase'])),
            ('desc', self.gf('django.db.models.fields.TextField')()),
            ('message', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='msgevents', null=True, to=orm['message.Message'])),
            ('in_reply_to', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='irtoevents', null=True, to=orm['message.Message'])),
            ('response_due', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'ipr', ['IprEvent'])

        # Adding model 'IprDocRel'
        db.create_table(u'ipr_iprdocrel', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('disclosure', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ipr.IprDisclosureBase'])),
            ('document', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['doc.DocAlias'])),
            ('sections', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('revisions', self.gf('django.db.models.fields.CharField')(max_length=16, blank=True)),
        ))
        db.send_create_signal(u'ipr', ['IprDocRel'])

        # Adding model 'ThirdPartyIprDisclosure'
        db.create_table(u'ipr_thirdpartyiprdisclosure', (
            (u'iprdisclosurebase_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ipr.IprDisclosureBase'], unique=True, primary_key=True)),
            ('ietfer_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('ietfer_contact_email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('ietfer_contact_info', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('patent_info', self.gf('django.db.models.fields.TextField')()),
            ('has_patent_pending', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'ipr', ['ThirdPartyIprDisclosure'])


    def backwards(self, orm):
        # Deleting model 'NonDocSpecificIprDisclosure'
        db.delete_table(u'ipr_nondocspecificiprdisclosure')

        # Deleting model 'RelatedIpr'
        db.delete_table(u'ipr_relatedipr')

        # Deleting model 'GenericIprDisclosure'
        db.delete_table(u'ipr_genericiprdisclosure')

        # Deleting model 'LegacyMigrationIprEvent'
        db.delete_table(u'ipr_legacymigrationiprevent')

        # Deleting model 'HolderIprDisclosure'
        db.delete_table(u'ipr_holderiprdisclosure')

        # Deleting model 'IprDisclosureBase'
        db.delete_table(u'ipr_iprdisclosurebase')

        # Deleting model 'IprEvent'
        db.delete_table(u'ipr_iprevent')

        # Deleting model 'IprDocRel'
        db.delete_table(u'ipr_iprdocrel')

        # Deleting model 'ThirdPartyIprDisclosure'
        db.delete_table(u'ipr_thirdpartyiprdisclosure')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'doc.docalias': {
            'Meta': {'object_name': 'DocAlias'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        u'doc.document': {
            'Meta': {'object_name': 'Document'},
            'abstract': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'ad_document_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
            'authors': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['person.Email']", 'symmetrical': 'False', 'through': u"orm['doc.DocumentAuthor']", 'blank': 'True'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'external_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'intended_std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IntendedStdLevelName']", 'null': 'True', 'blank': 'True'}),
            'internal_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'notify': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1', 'blank': 'True'}),
            'pages': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_document_set'", 'null': 'True', 'to': u"orm['person.Email']"}),
            'states': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'std_level': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StdLevelName']", 'null': 'True', 'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.StreamName']", 'null': 'True', 'blank': 'True'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['name.DocTagName']", 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocTypeName']", 'null': 'True', 'blank': 'True'})
        },
        u'doc.documentauthor': {
            'Meta': {'ordering': "['document', 'order']", 'object_name': 'DocumentAuthor'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Email']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'doc.state': {
            'Meta': {'ordering': "['type', 'order']", 'object_name': 'State'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'next_states': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'previous_states'", 'blank': 'True', 'to': u"orm['doc.State']"}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.StateType']"}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'doc.statetype': {
            'Meta': {'object_name': 'StateType'},
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '30', 'primary_key': 'True'})
        },
        u'group.group': {
            'Meta': {'object_name': 'Group'},
            'acronym': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '40'}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True', 'blank': 'True'}),
            'charter': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'chartered_group'", 'unique': 'True', 'null': 'True', 'to': u"orm['doc.Document']"}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'list_archive': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'list_email': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'list_subscribe': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.GroupStateName']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.GroupTypeName']", 'null': 'True'}),
            'unused_states': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.State']", 'symmetrical': 'False', 'blank': 'True'}),
            'unused_tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['name.DocTagName']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'ipr.genericiprdisclosure': {
            'Meta': {'object_name': 'GenericIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'statement': ('django.db.models.fields.TextField', [], {})
        },
        u'ipr.holderiprdisclosure': {
            'Meta': {'object_name': 'HolderIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'ietfer_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'ietfer_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ietfer_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'licensing': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprLicenseTypeName']"}),
            'licensing_comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'limited_to_std_track': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'patent_info': ('django.db.models.fields.TextField', [], {}),
            'submitter_claims_all_terms_disclosed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'ipr.iprcontact': {
            'Meta': {'object_name': 'IprContact'},
            'address1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'address2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'contact_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'contact_type': ('django.db.models.fields.IntegerField', [], {}),
            'department': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '255'}),
            'fax': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'contact'", 'to': u"orm['ipr.IprDetail']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'telephone': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'ipr.iprdetail': {
            'Meta': {'object_name': 'IprDetail'},
            'applies_to_all': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_column': "'selectowned'", 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'comply': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'date_applied': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'document_sections': ('django.db.models.fields.TextField', [], {'max_length': '255', 'db_column': "'disclouser_identify'", 'blank': 'True'}),
            'generic': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id_document_tag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'ipr_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_pending': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_column': "'selecttype'", 'blank': 'True'}),
            'legacy_title_1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_title1'", 'blank': 'True'}),
            'legacy_title_2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_title2'", 'blank': 'True'}),
            'legacy_url_0': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'old_ipr_url'", 'blank': 'True'}),
            'legacy_url_1': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_url1'", 'blank': 'True'}),
            'legacy_url_2': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'additional_old_url2'", 'blank': 'True'}),
            'legal_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'p_h_legal_name'"}),
            'lic_checkbox': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lic_opt_a_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'lic_opt_b_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'lic_opt_c_sub': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'licensing_option': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'db_column': "'p_notes'", 'blank': 'True'}),
            'other_designations': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'other_notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'patents': ('django.db.models.fields.TextField', [], {'max_length': '255', 'db_column': "'p_applications'"}),
            'rfc_number': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'submitted_date': ('django.db.models.fields.DateField', [], {'blank': 'True'}),
            'third_party': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'document_title'", 'blank': 'True'}),
            'update_notified_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        u'ipr.iprdisclosurebase': {
            'Meta': {'object_name': 'IprDisclosureBase'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'compliant': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'docs': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.DocAlias']", 'through': u"orm['ipr.IprDocRel']", 'symmetrical': 'False'}),
            'holder_legal_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'other_designations': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'rel': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'through': u"orm['ipr.RelatedIpr']", 'symmetrical': 'False'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprDisclosureStateName']"}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'submitter_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'ipr.iprdocalias': {
            'Meta': {'object_name': 'IprDocAlias'},
            'doc_alias': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocAlias']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDetail']"}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'})
        },
        u'ipr.iprdocrel': {
            'Meta': {'object_name': 'IprDocRel'},
            'disclosure': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDisclosureBase']"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.DocAlias']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'revisions': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'sections': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'ipr.iprevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'IprEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'desc': ('django.db.models.fields.TextField', [], {}),
            'disclosure': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDisclosureBase']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_reply_to': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'irtoevents'", 'null': 'True', 'to': u"orm['message.Message']"}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'msgevents'", 'null': 'True', 'to': u"orm['message.Message']"}),
            'response_due': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.IprEventTypeName']"})
        },
        u'ipr.iprnotification': {
            'Meta': {'object_name': 'IprNotification'},
            'date_sent': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['ipr.IprDetail']"}),
            'notification': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'time_sent': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'})
        },
        u'ipr.iprupdate': {
            'Meta': {'object_name': 'IprUpdate'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipr': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updates'", 'to': u"orm['ipr.IprDetail']"}),
            'processed': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'status_to_be': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updated_by'", 'db_column': "'updated'", 'to': u"orm['ipr.IprDetail']"})
        },
        u'ipr.legacymigrationiprevent': {
            'Meta': {'ordering': "['-time', '-id']", 'object_name': 'LegacyMigrationIprEvent', '_ormbases': [u'ipr.IprEvent']},
            u'iprevent_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprEvent']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'ipr.nondocspecificiprdisclosure': {
            'Meta': {'object_name': 'NonDocSpecificIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'holder_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'holder_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'holder_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'patent_info': ('django.db.models.fields.TextField', [], {}),
            'statement': ('django.db.models.fields.TextField', [], {})
        },
        u'ipr.relatedipr': {
            'Meta': {'object_name': 'RelatedIpr'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relatedipr_source_set'", 'to': u"orm['ipr.IprDisclosureBase']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relatedipr_target_set'", 'to': u"orm['ipr.IprDisclosureBase']"})
        },
        u'ipr.thirdpartyiprdisclosure': {
            'Meta': {'object_name': 'ThirdPartyIprDisclosure', '_ormbases': [u'ipr.IprDisclosureBase']},
            'has_patent_pending': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ietfer_contact_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'ietfer_contact_info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ietfer_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'iprdisclosurebase_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['ipr.IprDisclosureBase']", 'unique': 'True', 'primary_key': 'True'}),
            'patent_info': ('django.db.models.fields.TextField', [], {})
        },
        u'message.message': {
            'Meta': {'ordering': "['time']", 'object_name': 'Message'},
            'bcc': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'body': ('django.db.models.fields.TextField', [], {}),
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'cc': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.CharField', [], {'default': "'text/plain'", 'max_length': '255', 'blank': 'True'}),
            'frm': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'related_docs': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.Document']", 'symmetrical': 'False', 'blank': 'True'}),
            'related_groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['group.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'reply_address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'reply_to': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'subject': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'to': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        u'name.docrelationshipname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocRelationshipName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'revname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctagname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTagName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.grouptypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.intendedstdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'IntendedStdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.iprdisclosurestatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprDisclosureStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.ipreventtypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprEventTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.iprlicensetypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'IprLicenseTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.stdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.streamname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StreamName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'person.email': {
            'Meta': {'object_name': 'Email'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'address': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        u'person.person': {
            'Meta': {'object_name': 'Person'},
            'address': ('django.db.models.fields.TextField', [], {'max_length': '255', 'blank': 'True'}),
            'affiliation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'ascii': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'ascii_short': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['ipr']