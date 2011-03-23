
from south.db import db
from django.db import models
from ietf.submit.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding field 'TempIdAuthors.middle_initial'
        db.add_column('temp_id_authors', 'middle_initial', orm['submit.tempidauthors:middle_initial'])
        
        # Adding field 'TempIdAuthors.name_suffix'
        db.add_column('temp_id_authors', 'name_suffix', orm['submit.tempidauthors:name_suffix'])
        
    
    
    def backwards(self, orm):
        
        # Deleting field 'TempIdAuthors.middle_initial'
        db.delete_column('temp_id_authors', 'middle_initial')
        
        # Deleting field 'TempIdAuthors.name_suffix'
        db.delete_column('temp_id_authors', 'name_suffix')
        
    
    
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
        'submit.idapproveddetail': {
            'Meta': {'db_table': "'id_approved_detail'"},
            'approved_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'approved_person_tag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'approved_status': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'recorded_by': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'submit.idsubmissiondetail': {
            'Meta': {'db_table': "'id_submission_detail'"},
            'abstract': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'auth_key': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'comment_to_sec': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'creation_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'error_message': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'file_type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'filesize': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'first_two_pages': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']", 'null': 'True', 'blank': 'True'}),
            'id_document_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'idnits_failed': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'idnits_message': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'invalid_version': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'last_updated_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'last_updated_time': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'man_posted_by': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'man_posted_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'remote_ip': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'revision': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['submit.IdSubmissionStatus']", 'null': 'True', 'db_column': "'status_id'", 'blank': 'True'}),
            'sub_email_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'submission_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'submission_hash': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'submission_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submitter_tag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'temp_id_document_tag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'txt_page_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'warning_message': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'wg_submission': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'submit.idsubmissionstatus': {
            'Meta': {'db_table': "'id_submission_status'"},
            'status_id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'status_value': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        'submit.tempidauthors': {
            'Meta': {'db_table': "'temp_id_authors'"},
            'author_order': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'email_address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'id_document_tag': ('django.db.models.fields.IntegerField', [], {}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'middle_initial': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_suffix': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['submit.IdSubmissionDetail']"})
        }
    }
    
    complete_apps = ['submit']
