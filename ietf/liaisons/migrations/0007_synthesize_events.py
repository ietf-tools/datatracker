# -*- coding: utf-8 -*-
import os
import datetime
import syslog
from south.v2 import DataMigration


class Migration(DataMigration):

    def create_logger(self):
        migration_file = os.path.abspath(__file__)
        self.logger_filename = '%s.txt' % os.path.splitext(migration_file)[0]
        self.logger = open(self.logger_filename, "a")
        self.logger.write("\n\n%s\n--------------------\n" % datetime.datetime.now())

    def close_logger(self):
        self.logger.close()
        print '%s:' % self.logger_filename
        syslog.syslog('%s:' % self.logger_filename)
        for line in open(self.logger_filename, "r"):
            print line,
            syslog.syslog(line)

    def forwards(self, orm):
        self.create_logger()
        submitted = orm['name.LiaisonStatementEventTypeName'].objects.get(slug='submit')
        modified = orm['name.LiaisonStatementEventTypeName'].objects.get(slug='modified')
        approved = orm['name.LiaisonStatementEventTypeName'].objects.get(slug='approved')
        approved_state = orm['name.LiaisonStatementState'].objects.get(slug='approved')
        system_user = orm['person.Person'].objects.get(name="(System)")
        for liaison in orm['liaisons.LiaisonStatement'].objects.all():
            if liaison.submitted:
                event, _ = orm['liaisons.LiaisonStatementEvent'].objects.get_or_create(
                    type=submitted,
                    statement=liaison,
                    desc='Liaison submitted',
                    by=system_user)
                event.time = liaison.submitted
                event.save()
                self.logger.write("Created a liaison submitted event with date: %s\n" % liaison.submitted)
            if liaison.modified:
                event, _ = orm['liaisons.LiaisonStatementEvent'].objects.get_or_create(
                    time=liaison.modified,
                    type=modified,
                    statement=liaison,
                    desc='Liaison modified',
                    by=system_user)
                event.time = liaison.modified
                event.save()
                self.logger.write("Created a liaison modified event with date: %s\n" % liaison.submitted)
            if liaison.approved:
                event, _ = orm['liaisons.LiaisonStatementEvent'].objects.get_or_create(
                    time=liaison.approved,
                    type=approved,
                    statement=liaison,
                    desc='Liaison approved',
                    by=system_user)
                event.time = liaison.approved
                event.save()
                liaison.state = approved_state
                liaison.save()
                self.logger.write("Created a liaison approved event with date: %s\n" % liaison.submitted)
        self.close_logger()

    def backwards(self, orm):
        "Write your backwards methods here."

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
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'shepherd_document_set'", 'null': 'True', 'to': u"orm['person.Person']"}),
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
        u'liaisons.liaisonstatement': {
            'Meta': {'object_name': 'LiaisonStatement'},
            'action_holder_contacts': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'action_taken': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'approved': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'attachments': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.Document']", 'symmetrical': 'False', 'through': u"orm['liaisons.LiaisonStatementAttachments']", 'blank': 'True'}),
            'body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cc_contacts': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'deadline': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'from_contact': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Email']", 'null': 'True', 'blank': 'True'}),
            'from_group': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'liaisonstatement_from_set'", 'null': 'True', 'to': u"orm['group.Group']"}),
            'from_groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'liaisonsatement_from_set'", 'blank': 'True', 'to': u"orm['group.Group']"}),
            'from_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'other_identifiers': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'purpose': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.LiaisonStatementPurposeName']"}),
            'related_to': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['liaisons.LiaisonStatement']", 'null': 'True', 'blank': 'True'}),
            'reply_to': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'response_contacts': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'default': "'pending'", 'to': u"orm['name.LiaisonStatementState']"}),
            'submitted': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'technical_contacts': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'to_contacts': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'to_group': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'liaisonstatement_to_set'", 'null': 'True', 'to': u"orm['group.Group']"}),
            'to_groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'liaisonsatement_to_set'", 'blank': 'True', 'to': u"orm['group.Group']"}),
            'to_name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'liaisons.liaisonstatementattachments': {
            'Meta': {'object_name': 'LiaisonStatementAttachments'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'removed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'statement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['liaisons.LiaisonStatement']"})
        },
        u'liaisons.liaisonstatementevent': {
            'Meta': {'object_name': 'LiaisonStatementEvent'},
            'by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'desc': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'statement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['liaisons.LiaisonStatement']"}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.LiaisonStatementEventTypeName']"})
        },
        u'liaisons.liaisonstatementgroupcontacts': {
            'Meta': {'object_name': 'LiaisonStatementGroupContacts'},
            'default_reply_to': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']", 'unique': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'liaisons.relatedliaisonstatement': {
            'Meta': {'object_name': 'RelatedLiaisonStatement'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'relationship': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.DocRelationshipName']"}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'source_of_set'", 'to': u"orm['liaisons.LiaisonStatement']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_of_set'", 'to': u"orm['liaisons.LiaisonStatement']"})
        },
        u'name.docrelationshipname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocRelationshipName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'revname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctagname': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTagName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.doctypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.grouptypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.intendedstdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'IntendedStdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.liaisonstatementeventtypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'LiaisonStatementEventTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.liaisonstatementpurposename': {
            'Meta': {'ordering': "['order']", 'object_name': 'LiaisonStatementPurposeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.stdlevelname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StdLevelName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.streamname': {
            'Meta': {'ordering': "['order']", 'object_name': 'StreamName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.liaisonstatementstate': {
            'Meta': {'ordering': "['order']", 'object_name': 'LiaisonStatementState'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '8', 'primary_key': 'True'}),
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

    complete_apps = ['liaisons']
    symmetrical = True
