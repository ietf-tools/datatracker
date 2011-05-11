
from south.db import db
from django.db import models
from ietf.ietfworkflows.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding ManyToManyField 'WGWorkflow.selected_tags'
        db.create_table('ietfworkflows_wgworkflow_selected_tags', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('wgworkflow', models.ForeignKey(orm.WGWorkflow, null=False)),
            ('annotationtag', models.ForeignKey(orm.AnnotationTag, null=False))
        ))
        
        # Adding ManyToManyField 'WGWorkflow.selected_states'
        db.create_table('ietfworkflows_wgworkflow_selected_states', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('wgworkflow', models.ForeignKey(orm.WGWorkflow, null=False)),
            ('state', models.ForeignKey(orm['workflows.State'], null=False))
        ))
        
    
    
    def backwards(self, orm):
        
        # Dropping ManyToManyField 'WGWorkflow.selected_tags'
        db.delete_table('ietfworkflows_wgworkflow_selected_tags')
        
        # Dropping ManyToManyField 'WGWorkflow.selected_states'
        db.delete_table('ietfworkflows_wgworkflow_selected_states')
        
    
    
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
            'selected_states': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['workflows.State']"}),
            'selected_tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['ietfworkflows.AnnotationTag']"}),
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
