# -*- coding: utf-8 -*-
from south.db import db
from south.v2 import SchemaMigration

class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'DocRelationshipName.slug'
        db.alter_column(u'name_docrelationshipname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'StreamName.slug'
        db.alter_column(u'name_streamname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'GroupStateName.slug'
        db.alter_column(u'name_groupstatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'LiaisonStatementPurposeName.slug'
        db.alter_column(u'name_liaisonstatementpurposename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'FeedbackType.slug'
        db.alter_column(u'name_feedbacktype', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'GroupMilestoneStateName.slug'
        db.alter_column(u'name_groupmilestonestatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'BallotPositionName.slug'
        db.alter_column(u'name_ballotpositionname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'DraftSubmissionStateName.slug'
        db.alter_column(u'name_draftsubmissionstatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'GroupTypeName.slug'
        db.alter_column(u'name_grouptypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'DocReminderTypeName.slug'
        db.alter_column(u'name_docremindertypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'MeetingTypeName.slug'
        db.alter_column(u'name_meetingtypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'DocTypeName.slug'
        db.alter_column(u'name_doctypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'IntendedStdLevelName.slug'
        db.alter_column(u'name_intendedstdlevelname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'StdLevelName.slug'
        db.alter_column(u'name_stdlevelname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'SessionStatusName.slug'
        db.alter_column(u'name_sessionstatusname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'NomineePositionState.slug'
        db.alter_column(u'name_nomineepositionstate', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'ConstraintName.slug'
        db.alter_column(u'name_constraintname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'RoleName.slug'
        db.alter_column(u'name_rolename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'DocTagName.slug'
        db.alter_column(u'name_doctagname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'RoomResourceName.slug'
        db.alter_column(u'name_roomresourcename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'DBTemplateTypeName.slug'
        db.alter_column(u'name_dbtemplatetypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

        # Changing field 'TimeSlotTypeName.slug'
        db.alter_column(u'name_timeslottypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=32, primary_key=True))

    def backwards(self, orm):

        # Changing field 'DocRelationshipName.slug'
        db.alter_column(u'name_docrelationshipname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'StreamName.slug'
        db.alter_column(u'name_streamname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'GroupStateName.slug'
        db.alter_column(u'name_groupstatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'LiaisonStatementPurposeName.slug'
        db.alter_column(u'name_liaisonstatementpurposename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'FeedbackType.slug'
        db.alter_column(u'name_feedbacktype', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'GroupMilestoneStateName.slug'
        db.alter_column(u'name_groupmilestonestatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'BallotPositionName.slug'
        db.alter_column(u'name_ballotpositionname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'DraftSubmissionStateName.slug'
        db.alter_column(u'name_draftsubmissionstatename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'GroupTypeName.slug'
        db.alter_column(u'name_grouptypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'DocReminderTypeName.slug'
        db.alter_column(u'name_docremindertypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'MeetingTypeName.slug'
        db.alter_column(u'name_meetingtypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'DocTypeName.slug'
        db.alter_column(u'name_doctypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'IntendedStdLevelName.slug'
        db.alter_column(u'name_intendedstdlevelname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'StdLevelName.slug'
        db.alter_column(u'name_stdlevelname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'SessionStatusName.slug'
        db.alter_column(u'name_sessionstatusname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'NomineePositionState.slug'
        db.alter_column(u'name_nomineepositionstate', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'ConstraintName.slug'
        db.alter_column(u'name_constraintname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'RoleName.slug'
        db.alter_column(u'name_rolename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'DocTagName.slug'
        db.alter_column(u'name_doctagname', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'RoomResourceName.slug'
        db.alter_column(u'name_roomresourcename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'DBTemplateTypeName.slug'
        db.alter_column(u'name_dbtemplatetypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

        # Changing field 'TimeSlotTypeName.slug'
        db.alter_column(u'name_timeslottypename', 'slug', self.gf('django.db.models.fields.CharField')(max_length=8, primary_key=True))

    models = {
        u'name.ballotpositionname': {
            'Meta': {'ordering': "['order']", 'object_name': 'BallotPositionName'},
            'blocking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
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
        u'name.dbtemplatetypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DBTemplateTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
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
        u'name.docremindertypename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DocReminderTypeName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
        u'name.draftsubmissionstatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'DraftSubmissionStateName'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'next_states': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'previous_states'", 'blank': 'True', 'to': u"orm['name.DraftSubmissionStateName']"}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.feedbacktype': {
            'Meta': {'ordering': "['order']", 'object_name': 'FeedbackType'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.groupmilestonestatename': {
            'Meta': {'ordering': "['order']", 'object_name': 'GroupMilestoneStateName'},
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
        u'name.liaisonstatementpurposename': {
            'Meta': {'ordering': "['order']", 'object_name': 'LiaisonStatementPurposeName'},
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
        u'name.nomineepositionstate': {
            'Meta': {'ordering': "['order']", 'object_name': 'NomineePositionState'},
            'desc': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'order': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '32', 'primary_key': 'True'}),
            'used': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'name.rolename': {
            'Meta': {'ordering': "['order']", 'object_name': 'RoleName'},
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
        }
    }

    complete_apps = ['name']