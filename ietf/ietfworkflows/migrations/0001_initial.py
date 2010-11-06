
from south.db import db
from django.db import models
from ietf.ietfworkflows.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'WGWorkflow'
        db.create_table('ietfworkflows_wgworkflow', (
            ('workflow_ptr', orm['ietfworkflows.WGWorkflow:workflow_ptr']),
        ))
        db.send_create_signal('ietfworkflows', ['WGWorkflow'])
        
        # Adding model 'ObjectWorkflowHistoryEntry'
        db.create_table('ietfworkflows_objectworkflowhistoryentry', (
            ('id', orm['ietfworkflows.ObjectWorkflowHistoryEntry:id']),
            ('content_type', orm['ietfworkflows.ObjectWorkflowHistoryEntry:content_type']),
            ('content_id', orm['ietfworkflows.ObjectWorkflowHistoryEntry:content_id']),
            ('from_state', orm['ietfworkflows.ObjectWorkflowHistoryEntry:from_state']),
            ('to_state', orm['ietfworkflows.ObjectWorkflowHistoryEntry:to_state']),
            ('transition_date', orm['ietfworkflows.ObjectWorkflowHistoryEntry:transition_date']),
            ('comment', orm['ietfworkflows.ObjectWorkflowHistoryEntry:comment']),
        ))
        db.send_create_signal('ietfworkflows', ['ObjectWorkflowHistoryEntry'])
        
        # Adding model 'ObjectAnnotationTagHistoryEntry'
        db.create_table('ietfworkflows_objectannotationtaghistoryentry', (
            ('id', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:id']),
            ('content_type', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:content_type']),
            ('content_id', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:content_id']),
            ('setted', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:setted']),
            ('unsetted', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:unsetted']),
            ('change_date', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:change_date']),
            ('comment', orm['ietfworkflows.ObjectAnnotationTagHistoryEntry:comment']),
        ))
        db.send_create_signal('ietfworkflows', ['ObjectAnnotationTagHistoryEntry'])
        
        # Adding model 'AnnotationTag'
        db.create_table('ietfworkflows_annotationtag', (
            ('id', orm['ietfworkflows.AnnotationTag:id']),
            ('name', orm['ietfworkflows.AnnotationTag:name']),
            ('workflow', orm['ietfworkflows.AnnotationTag:workflow']),
            ('permission', orm['ietfworkflows.AnnotationTag:permission']),
        ))
        db.send_create_signal('ietfworkflows', ['AnnotationTag'])
        
        # Adding model 'AnnotationTagObjectRelation'
        db.create_table('ietfworkflows_annotationtagobjectrelation', (
            ('id', orm['ietfworkflows.AnnotationTagObjectRelation:id']),
            ('content_type', orm['ietfworkflows.AnnotationTagObjectRelation:content_type']),
            ('content_id', orm['ietfworkflows.AnnotationTagObjectRelation:content_id']),
            ('annotation_tag', orm['ietfworkflows.AnnotationTagObjectRelation:annotation_tag']),
        ))
        db.send_create_signal('ietfworkflows', ['AnnotationTagObjectRelation'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'WGWorkflow'
        db.delete_table('ietfworkflows_wgworkflow')
        
        # Deleting model 'ObjectWorkflowHistoryEntry'
        db.delete_table('ietfworkflows_objectworkflowhistoryentry')
        
        # Deleting model 'ObjectAnnotationTagHistoryEntry'
        db.delete_table('ietfworkflows_objectannotationtaghistoryentry')
        
        # Deleting model 'AnnotationTag'
        db.delete_table('ietfworkflows_annotationtag')
        
        # Deleting model 'AnnotationTagObjectRelation'
        db.delete_table('ietfworkflows_annotationtagobjectrelation')
        
    
    
    models = {
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'ietfworkflows.annotationtag': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']", 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'annotation_tags'", 'to': "orm['workflows.Workflow']"})
        },
        'ietfworkflows.annotationtagobjectrelation': {
            'annotation_tag': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ietfworkflows.AnnotationTag']"}),
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'annotation_tags'", 'null': 'True', 'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'ietfworkflows.objectannotationtaghistoryentry': {
            'change_date': ('django.db.models.fields.DateTimeField', [], {}),
            'comment': ('django.db.models.fields.TextField', [], {}),
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'annotation_tags_history'", 'null': 'True', 'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'setted': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'unsetted': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'ietfworkflows.objectworkflowhistoryentry': {
            'comment': ('django.db.models.fields.TextField', [], {}),
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'workflow_history'", 'null': 'True', 'to': "orm['contenttypes.ContentType']"}),
            'from_state': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'to_state': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'transition_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'ietfworkflows.wgworkflow': {
            'workflow_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['workflows.Workflow']", 'unique': 'True', 'primary_key': 'True'})
        },
        'permissions.permission': {
            'codename': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'content_types': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'workflows.state': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'transitions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['workflows.Transition']", 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'states'", 'to': "orm['workflows.Workflow']"})
        },
        'workflows.transition': {
            'condition': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'destination': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'destination_state'", 'null': 'True', 'to': "orm['workflows.State']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']", 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'transitions'", 'to': "orm['workflows.Workflow']"})
        },
        'workflows.workflow': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'initial_state': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'workflow_state'", 'null': 'True', 'to': "orm['workflows.State']"}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['permissions.Permission']", 'symmetrical': 'False'})
        }
    }
    
    complete_apps = ['ietfworkflows']
