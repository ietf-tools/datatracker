
from south.db import db
from django.db import models
from ietf.wgchairs.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'ProtoWriteUp'
        db.create_table('wgchairs_protowriteup', (
            ('id', orm['wgchairs.protowriteup:id']),
            ('person', orm['wgchairs.protowriteup:person']),
            ('draft', orm['wgchairs.protowriteup:draft']),
            ('date', orm['wgchairs.protowriteup:date']),
            ('writeup', orm['wgchairs.protowriteup:writeup']),
        ))
        db.send_create_signal('wgchairs', ['ProtoWriteUp'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'ProtoWriteUp'
        db.delete_table('wgchairs_protowriteup')
        
    
    
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
        'idtracker.idintendedstatus': {
            'Meta': {'db_table': "'id_intended_status'"},
            'intended_status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'intended_status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.idstatus': {
            'Meta': {'db_table': "'id_status'"},
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
        'idtracker.internetdraft': {
            'Meta': {'db_table': "'internet_drafts'"},
            'abstract': ('django.db.models.fields.TextField', [], {}),
            'b_approve_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'b_discussion_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'b_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'dunn_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'expiration_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'expired_tombstone': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'extension_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'file_type': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'filename': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.Acronym']", 'db_column': "'group_acronym_id'"}),
            'id_document_key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id_document_tag': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'intended_status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IDIntendedStatus']"}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {}),
            'lc_changes': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True'}),
            'lc_expiration_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'lc_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'local_path': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'replaced_by': ('django.db.models.fields.related.ForeignKey', ["orm['idtracker.InternetDraft']"], {'related_name': "'replaces_set'", 'null': 'True', 'db_column': "'replaced_by'", 'blank': 'True'}),
            'review_by_rfc_editor': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'revision': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'revision_date': ('django.db.models.fields.DateField', [], {}),
            'rfc_number': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'null': 'True', 'blank': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IDStatus']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'id_document_name'"}),
            'txt_page_count': ('django.db.models.fields.IntegerField', [], {}),
            'wgreturn_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
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
        'wgchairs.protowriteup': {
            'date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now()'}),
            'draft': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.InternetDraft']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']"}),
            'writeup': ('django.db.models.fields.TextField', [], {})
        },
        'wgchairs.wgdelegate': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']"}),
            'wg': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"})
        }
    }
    
    complete_apps = ['wgchairs']
