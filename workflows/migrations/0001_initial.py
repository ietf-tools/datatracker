
from south.db import db
from django.db import models
from workflows.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'Workflow'
        db.create_table('workflows_workflow', (
            ('id', orm['workflows.Workflow:id']),
            ('name', orm['workflows.Workflow:name']),
            ('initial_state', orm['workflows.Workflow:initial_state']),
        ))
        db.send_create_signal('workflows', ['Workflow'])
        
        # Adding model 'StatePermissionRelation'
        db.create_table('workflows_statepermissionrelation', (
            ('id', orm['workflows.StatePermissionRelation:id']),
            ('state', orm['workflows.StatePermissionRelation:state']),
            ('permission', orm['workflows.StatePermissionRelation:permission']),
            ('role', orm['workflows.StatePermissionRelation:role']),
        ))
        db.send_create_signal('workflows', ['StatePermissionRelation'])
        
        # Adding model 'StateInheritanceBlock'
        db.create_table('workflows_stateinheritanceblock', (
            ('id', orm['workflows.StateInheritanceBlock:id']),
            ('state', orm['workflows.StateInheritanceBlock:state']),
            ('permission', orm['workflows.StateInheritanceBlock:permission']),
        ))
        db.send_create_signal('workflows', ['StateInheritanceBlock'])
        
        # Adding model 'WorkflowModelRelation'
        db.create_table('workflows_workflowmodelrelation', (
            ('id', orm['workflows.WorkflowModelRelation:id']),
            ('content_type', orm['workflows.WorkflowModelRelation:content_type']),
            ('workflow', orm['workflows.WorkflowModelRelation:workflow']),
        ))
        db.send_create_signal('workflows', ['WorkflowModelRelation'])
        
        # Adding model 'WorkflowPermissionRelation'
        db.create_table('workflows_workflowpermissionrelation', (
            ('id', orm['workflows.WorkflowPermissionRelation:id']),
            ('workflow', orm['workflows.WorkflowPermissionRelation:workflow']),
            ('permission', orm['workflows.WorkflowPermissionRelation:permission']),
        ))
        db.send_create_signal('workflows', ['WorkflowPermissionRelation'])
        
        # Adding model 'State'
        db.create_table('workflows_state', (
            ('id', orm['workflows.State:id']),
            ('name', orm['workflows.State:name']),
            ('workflow', orm['workflows.State:workflow']),
        ))
        db.send_create_signal('workflows', ['State'])
        
        # Adding model 'Transition'
        db.create_table('workflows_transition', (
            ('id', orm['workflows.Transition:id']),
            ('name', orm['workflows.Transition:name']),
            ('workflow', orm['workflows.Transition:workflow']),
            ('destination', orm['workflows.Transition:destination']),
            ('condition', orm['workflows.Transition:condition']),
            ('permission', orm['workflows.Transition:permission']),
        ))
        db.send_create_signal('workflows', ['Transition'])
        
        # Adding model 'WorkflowObjectRelation'
        db.create_table('workflows_workflowobjectrelation', (
            ('id', orm['workflows.WorkflowObjectRelation:id']),
            ('content_type', orm['workflows.WorkflowObjectRelation:content_type']),
            ('content_id', orm['workflows.WorkflowObjectRelation:content_id']),
            ('workflow', orm['workflows.WorkflowObjectRelation:workflow']),
        ))
        db.send_create_signal('workflows', ['WorkflowObjectRelation'])
        
        # Adding model 'StateObjectRelation'
        db.create_table('workflows_stateobjectrelation', (
            ('id', orm['workflows.StateObjectRelation:id']),
            ('content_type', orm['workflows.StateObjectRelation:content_type']),
            ('content_id', orm['workflows.StateObjectRelation:content_id']),
            ('state', orm['workflows.StateObjectRelation:state']),
        ))
        db.send_create_signal('workflows', ['StateObjectRelation'])
        
        # Adding ManyToManyField 'State.transitions'
        db.create_table('workflows_state_transitions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('state', models.ForeignKey(orm.State, null=False)),
            ('transition', models.ForeignKey(orm.Transition, null=False))
        ))
        
        # Creating unique_together for [content_type, content_id] on WorkflowObjectRelation.
        db.create_unique('workflows_workflowobjectrelation', ['content_type_id', 'content_id'])
        
        # Creating unique_together for [content_type, content_id, state] on StateObjectRelation.
        db.create_unique('workflows_stateobjectrelation', ['content_type_id', 'content_id', 'state_id'])
        
        # Creating unique_together for [workflow, permission] on WorkflowPermissionRelation.
        db.create_unique('workflows_workflowpermissionrelation', ['workflow_id', 'permission_id'])
        
    
    
    def backwards(self, orm):
        
        # Deleting unique_together for [workflow, permission] on WorkflowPermissionRelation.
        db.delete_unique('workflows_workflowpermissionrelation', ['workflow_id', 'permission_id'])
        
        # Deleting unique_together for [content_type, content_id, state] on StateObjectRelation.
        db.delete_unique('workflows_stateobjectrelation', ['content_type_id', 'content_id', 'state_id'])
        
        # Deleting unique_together for [content_type, content_id] on WorkflowObjectRelation.
        db.delete_unique('workflows_workflowobjectrelation', ['content_type_id', 'content_id'])
        
        # Deleting model 'Workflow'
        db.delete_table('workflows_workflow')
        
        # Deleting model 'StatePermissionRelation'
        db.delete_table('workflows_statepermissionrelation')
        
        # Deleting model 'StateInheritanceBlock'
        db.delete_table('workflows_stateinheritanceblock')
        
        # Deleting model 'WorkflowModelRelation'
        db.delete_table('workflows_workflowmodelrelation')
        
        # Deleting model 'WorkflowPermissionRelation'
        db.delete_table('workflows_workflowpermissionrelation')
        
        # Deleting model 'State'
        db.delete_table('workflows_state')
        
        # Deleting model 'Transition'
        db.delete_table('workflows_transition')
        
        # Deleting model 'WorkflowObjectRelation'
        db.delete_table('workflows_workflowobjectrelation')
        
        # Deleting model 'StateObjectRelation'
        db.delete_table('workflows_stateobjectrelation')
        
        # Dropping ManyToManyField 'State.transitions'
        db.delete_table('workflows_state_transitions')
        
    
    
    models = {
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'permissions.permission': {
            'codename': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'content_types': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'permissions.role': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'workflows.state': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'transitions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['workflows.Transition']", 'null': 'True', 'blank': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'states'", 'to': "orm['workflows.Workflow']"})
        },
        'workflows.stateinheritanceblock': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']"}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['workflows.State']"})
        },
        'workflows.stateobjectrelation': {
            'Meta': {'unique_together': "(('content_type', 'content_id', 'state'),)"},
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'state_object'", 'null': 'True', 'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['workflows.State']"})
        },
        'workflows.statepermissionrelation': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']"}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Role']"}),
            'state': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['workflows.State']"})
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
        },
        'workflows.workflowmodelrelation': {
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'unique': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'wmrs'", 'to': "orm['workflows.Workflow']"})
        },
        'workflows.workflowobjectrelation': {
            'Meta': {'unique_together': "(('content_type', 'content_id'),)"},
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'workflow_object'", 'null': 'True', 'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'wors'", 'to': "orm['workflows.Workflow']"})
        },
        'workflows.workflowpermissionrelation': {
            'Meta': {'unique_together': "(('workflow', 'permission'),)"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'permissions'", 'to': "orm['permissions.Permission']"}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['workflows.Workflow']"})
        }
    }
    
    complete_apps = ['workflows']
