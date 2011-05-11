
from south.db import db
from django.db import models
from permissions.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'Role'
        db.create_table('permissions_role', (
            ('id', orm['permissions.Role:id']),
            ('name', orm['permissions.Role:name']),
        ))
        db.send_create_signal('permissions', ['Role'])
        
        # Adding model 'ObjectPermissionInheritanceBlock'
        db.create_table('permissions_objectpermissioninheritanceblock', (
            ('id', orm['permissions.ObjectPermissionInheritanceBlock:id']),
            ('permission', orm['permissions.ObjectPermissionInheritanceBlock:permission']),
            ('content_type', orm['permissions.ObjectPermissionInheritanceBlock:content_type']),
            ('content_id', orm['permissions.ObjectPermissionInheritanceBlock:content_id']),
        ))
        db.send_create_signal('permissions', ['ObjectPermissionInheritanceBlock'])
        
        # Adding model 'ObjectPermission'
        db.create_table('permissions_objectpermission', (
            ('id', orm['permissions.ObjectPermission:id']),
            ('role', orm['permissions.ObjectPermission:role']),
            ('permission', orm['permissions.ObjectPermission:permission']),
            ('content_type', orm['permissions.ObjectPermission:content_type']),
            ('content_id', orm['permissions.ObjectPermission:content_id']),
        ))
        db.send_create_signal('permissions', ['ObjectPermission'])
        
        # Adding model 'Permission'
        db.create_table('permissions_permission', (
            ('id', orm['permissions.Permission:id']),
            ('name', orm['permissions.Permission:name']),
            ('codename', orm['permissions.Permission:codename']),
        ))
        db.send_create_signal('permissions', ['Permission'])
        
        # Adding model 'PrincipalRoleRelation'
        db.create_table('permissions_principalrolerelation', (
            ('id', orm['permissions.PrincipalRoleRelation:id']),
            ('user', orm['permissions.PrincipalRoleRelation:user']),
            ('group', orm['permissions.PrincipalRoleRelation:group']),
            ('role', orm['permissions.PrincipalRoleRelation:role']),
            ('content_type', orm['permissions.PrincipalRoleRelation:content_type']),
            ('content_id', orm['permissions.PrincipalRoleRelation:content_id']),
        ))
        db.send_create_signal('permissions', ['PrincipalRoleRelation'])
        
        # Adding ManyToManyField 'Permission.content_types'
        db.create_table('permissions_permission_content_types', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('permission', models.ForeignKey(orm.Permission, null=False)),
            ('contenttype', models.ForeignKey(orm['contenttypes.ContentType'], null=False))
        ))
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'Role'
        db.delete_table('permissions_role')
        
        # Deleting model 'ObjectPermissionInheritanceBlock'
        db.delete_table('permissions_objectpermissioninheritanceblock')
        
        # Deleting model 'ObjectPermission'
        db.delete_table('permissions_objectpermission')
        
        # Deleting model 'Permission'
        db.delete_table('permissions_permission')
        
        # Deleting model 'PrincipalRoleRelation'
        db.delete_table('permissions_principalrolerelation')
        
        # Dropping ManyToManyField 'Permission.content_types'
        db.delete_table('permissions_permission_content_types')
        
    
    
    models = {
        'auth.group': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)"},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'permissions.objectpermission': {
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']"}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Role']", 'null': 'True', 'blank': 'True'})
        },
        'permissions.objectpermissioninheritanceblock': {
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Permission']"})
        },
        'permissions.permission': {
            'codename': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'content_types': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'permissions.principalrolerelation': {
            'content_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['permissions.Role']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'permissions.role': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        }
    }
    
    complete_apps = ['permissions']
