# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing foreign key 'Submission.state'
        db.alter_column(u'submit_submission', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'LiaisonStatement.purpose'
        db.alter_column(u'liaisons_liaisonstatement', 'purpose_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Meeting.type'
        db.alter_column(u'meeting_meeting', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'ResourceAssociation.name'
        db.alter_column(u'meeting_resourceassociation', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'TimeSlot.type'
        db.alter_column(u'meeting_timeslot', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Constraint.name'
        db.alter_column(u'meeting_constraint', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Session.status'
        db.alter_column(u'meeting_session', 'status_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Document.type'
        db.alter_column(u'doc_document', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Document.stream'
        db.alter_column(u'doc_document', 'stream_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Document.std_level'
        db.alter_column(u'doc_document', 'std_level_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DocumentHistory.type'
        db.alter_column(u'doc_documenthistory', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DocumentHistory.stream'
        db.alter_column(u'doc_documenthistory', 'stream_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DocumentHistory.intended_std_level'
        db.alter_column(u'doc_documenthistory', 'intended_std_level_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DocumentHistory.std_level'
        db.alter_column(u'doc_documenthistory', 'std_level_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'RelatedDocument.relationship'
        db.alter_column(u'doc_relateddocument', 'relationship_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'RelatedDocHistory.relationship'
        db.alter_column(u'doc_relateddochistory', 'relationship_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DocReminder.type'
        db.alter_column(u'doc_docreminder', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'BallotType.doc_type'
        db.alter_column(u'doc_ballottype', 'doc_type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'BallotPositionDocEvent.pos'
        db.alter_column(u'doc_ballotpositiondocevent', 'pos_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'DBTemplate.'
        db.alter_column(u'dbtemplate_dbtemplate', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Group.state'
        db.alter_column(u'group_group', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Group.type'
        db.alter_column(u'group_group', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'GroupHistory.state'
        db.alter_column(u'group_grouphistory', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'GroupHistory.type'
        db.alter_column(u'group_grouphistory', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'GroupMilestone.state'
        db.alter_column(u'group_groupmilestone', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'GroupMilestoneHistory.state'
        db.alter_column(u'group_groupmilestonehistory', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'ChangeStateGroupEvent.state'
        db.alter_column(u'group_changestategroupevent', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Role.name'
        db.alter_column(u'group_role', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'RoleHistory.name'
        db.alter_column(u'group_rolehistory', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=32))

        # Changing foreign key 'Feedback.type'
        db.alter_column(u'nomcom_feedback', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=32))


    def backwards(self, orm):

        # Changing foreign key 'Submission.state'
        db.alter_column(u'submit_submission', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'LiaisonStatement.purpose'
        db.alter_column(u'liaisons_liaisonstatement', 'purpose_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Meeting.type'
        db.alter_column(u'meeting_meeting', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'ResourceAssociation.name'
        db.alter_column(u'meeting_resourceassociation', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'TimeSlot.type'
        db.alter_column(u'meeting_timeslot', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Constraint.name'
        db.alter_column(u'meeting_constraint', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Session.status'
        db.alter_column(u'meeting_session', 'status_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Document.type'
        db.alter_column(u'doc_document', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Document.stream'
        db.alter_column(u'doc_document', 'stream_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Document.std_level'
        db.alter_column(u'doc_document', 'std_level_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DocumentHistory.type'
        db.alter_column(u'doc_documenthistory', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DocumentHistory.stream'
        db.alter_column(u'doc_documenthistory', 'stream_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DocumentHistory.intended_std_level'
        db.alter_column(u'doc_documenthistory', 'intended_std_level_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DocumentHistory.std_level'
        db.alter_column(u'doc_documenthistory', 'std_level_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'RelatedDocument.relationship'
        db.alter_column(u'doc_relateddocument', 'relationship_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'RelatedDocHistory.relationship'
        db.alter_column(u'doc_relateddochistory', 'relationship_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DocReminder.type'
        db.alter_column(u'doc_docreminder', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'BallotType.doc_type'
        db.alter_column(u'doc_ballottype', 'doc_type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'BallotPositionDocEvent.pos'
        db.alter_column(u'doc_ballotpositiondocevent', 'pos_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'DBTemplate.'
        db.alter_column(u'dbtemplate_dbtemplate', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Group.state'
        db.alter_column(u'group_group', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Group.type'
        db.alter_column(u'group_group', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'GroupHistory.state'
        db.alter_column(u'group_grouphistory', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'GroupHistory.type'
        db.alter_column(u'group_grouphistory', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'GroupMilestone.state'
        db.alter_column(u'group_groupmilestone', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'GroupMilestoneHistory.state'
        db.alter_column(u'group_groupmilestonehistory', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'ChangeStateGroupEvent.state'
        db.alter_column(u'group_changestategroupevent', 'state_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Role.name'
        db.alter_column(u'group_role', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'RoleHistory.name'
        db.alter_column(u'group_rolehistory', 'name_id', self.gf('django.db.models.fields.CharField')(max_length=8))

        # Changing foreign key 'Feedback.type'
        db.alter_column(u'nomcom_feedback', 'type_id', self.gf('django.db.models.fields.CharField')(max_length=8))


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