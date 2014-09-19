# -*- coding: utf-8 -*-
from south.v2 import DataMigration

class Migration(DataMigration):

    def forwards(self, orm):
        for vm in orm['meeting.SessionPresentation'].objects.all():
            vm.rev = vm.document.rev
            vm.save()

    def backwards(self, orm):
        pass

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
        u'meeting.constraint': {
            'Meta': {'object_name': 'Constraint'},
            'day': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meeting': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Meeting']"}),
            'name': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.ConstraintName']"}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']", 'null': 'True', 'blank': 'True'}),
            'source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'constraint_source_set'", 'to': u"orm['group.Group']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'constraint_target_set'", 'null': 'True', 'to': u"orm['group.Group']"})
        },
        u'meeting.meeting': {
            'Meta': {'ordering': "['-date']", 'object_name': 'Meeting'},
            'agenda': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': u"orm['meeting.Schedule']"}),
            'agenda_note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'break_area': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'reg_area': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'time_zone': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.MeetingTypeName']"}),
            'venue_addr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'venue_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'meeting.resourceassociation': {
            'Meta': {'object_name': 'ResourceAssociation'},
            'desc': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'icon': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.RoomResourceName']"})
        },
        u'meeting.room': {
            'Meta': {'object_name': 'Room'},
            'capacity': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meeting': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Meeting']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'resources': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['meeting.ResourceAssociation']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'meeting.schedule': {
            'Meta': {'object_name': 'Schedule'},
            'badness': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meeting': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Meeting']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'visible': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'meeting.scheduledsession': {
            'Meta': {'ordering': "['timeslot__time', 'session__group__parent__name', 'session__group__acronym', 'session__name']", 'object_name': 'ScheduledSession'},
            'badness': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'extendedfrom': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['meeting.ScheduledSession']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'pinned': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'schedule': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'assignments'", 'to': u"orm['meeting.Schedule']"}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['meeting.Session']", 'null': 'True'}),
            'timeslot': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.TimeSlot']"})
        },
        u'meeting.session': {
            'Meta': {'object_name': 'Session'},
            'agenda_note': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'attendees': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['group.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'materials': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['doc.Document']", 'symmetrical': 'False', 'through': u"orm['meeting.SessionPresentation']", 'blank': 'True'}),
            'meeting': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Meeting']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'requested': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'requested_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['person.Person']"}),
            'requested_duration': ('ietf.meeting.timedeltafield.TimedeltaField', [], {'default': '0'}),
            'resources': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['meeting.ResourceAssociation']", 'symmetrical': 'False'}),
            'scheduled': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'short': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.SessionStatusName']"})
        },
        u'meeting.timeslot': {
            'Meta': {'object_name': 'TimeSlot'},
            'duration': ('ietf.meeting.timedeltafield.TimedeltaField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Room']", 'null': 'True', 'blank': 'True'}),
            'meeting': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Meeting']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'slots'", 'to': u"orm['meeting.Session']", 'through': u"orm['meeting.ScheduledSession']", 'blank': 'True', 'symmetrical': 'False', 'null': 'True'}),
            'show_location': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['name.TimeSlotTypeName']"})
        },
        u'meeting.sessionpresentation': {
            'Meta': {'object_name': 'SessionPresentation', 'db_table': "'meeting_session_materials'"},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['doc.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rev': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['meeting.Session']"})
        },
        u'name.constraintname': {
            'Meta': {'ordering': "['order']", 'object_name': 'ConstraintName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'penalty': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
        u'name.meetingtypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'MeetingTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.roomresourcename': {
            'Meta': {'ordering': "['order']", 'object_name': 'RoomResourceName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.sessionstatusname': {
            'Meta': {'ordering': "['order']", 'object_name': 'SessionStatusName'},
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
        u'name.timeslottypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'TimeSlotTypeName'},
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

    complete_apps = ['meeting']
    symmetrical = True
