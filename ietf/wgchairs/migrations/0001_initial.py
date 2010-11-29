
from south.db import db
from django.db import models
from ietf.wgchairs.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'WGDelegate'
        db.create_table('wgchairs_wgdelegate', (
            ('id', orm['wgchairs.WGDelegate:id']),
            ('person', orm['wgchairs.WGDelegate:person']),
            ('wg', orm['wgchairs.WGDelegate:wg']),
        ))
        db.send_create_signal('wgchairs', ['WGDelegate'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'WGDelegate'
        db.delete_table('wgchairs_wgdelegate')
        
    
    
    models = {
        'idtracker.acronym': {
            'Meta': {'db_table': "'acronym'"},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
            'acronym_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_key': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'idtracker.area': {
            'Meta': {'db_table': "'areas'"},
            'area_acronym': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['idtracker.Acronym']", 'unique': 'True', 'primary_key': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'concluded_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'extra_email_addresses': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.AreaStatus']"})
        },
        'idtracker.areadirector': {
            'Meta': {'db_table': "'area_directors'"},
            'area': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.Area']", 'null': 'True', 'db_column': "'area_acronym_id'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.areastatus': {
            'Meta': {'db_table': "'area_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.ietfwg': {
            'Meta': {'db_table': "'groups_ietf'"},
            'area_director': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.AreaDirector']", 'null': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'concluded_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'dormant_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'email_address': ('django.db.models.fields.CharField', [], {'max_length': '60', 'blank': 'True'}),
            'email_archive': ('django.db.models.fields.CharField', [], {'max_length': '95', 'blank': 'True'}),
            'email_keyword': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'email_subscribe': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'group_acronym': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['idtracker.Acronym']", 'unique': 'True', 'primary_key': 'True'}),
            'group_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.WGType']"}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {}),
            'meeting_scheduled': ('django.db.models.fields.CharField', [], {'max_length': '3', 'blank': 'True'}),
            'meeting_scheduled_old': ('django.db.models.fields.CharField', [], {'max_length': '3', 'blank': 'True'}),
            'proposed_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.WGStatus']"})
        },
        'idtracker.personororginfo': {
            'Meta': {'db_table': "'person_or_org_info'"},
            'address_type': ('django.db.models.fields.CharField', [], {'max_length': '4', 'null': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'first_name_key': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'last_name_key': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'middle_initial': ('django.db.models.fields.CharField', [], {'max_length': '4', 'null': 'True', 'blank': 'True'}),
            'middle_initial_key': ('django.db.models.fields.CharField', [], {'max_length': '4', 'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'}),
            'name_prefix': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'name_suffix': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'person_or_org_tag': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'record_type': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'})
        },
        'idtracker.wgstatus': {
            'Meta': {'db_table': "'g_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.wgtype': {
            'Meta': {'db_table': "'g_type'"},
            'group_type_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'group_type'"})
        },
        'wgchairs.wgdelegate': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']"}),
            'wg': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"})
        }
    }
    
    complete_apps = ['wgchairs']
