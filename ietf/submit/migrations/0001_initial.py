
from south.db import db
from django.db import models, connection
from ietf.submit.models import *

class Migration:
    
    def forwards(self, orm):
        
        if 'id_submission_detail' in connection.introspection.get_table_list(connection.cursor()):
            return # already migrated

        # Adding model 'TempIdAuthors'
        db.create_table('temp_id_authors', (
            ('id', orm['submit.TempIdAuthors:id']),
            ('id_document_tag', orm['submit.TempIdAuthors:id_document_tag']),
            ('first_name', orm['submit.TempIdAuthors:first_name']),
            ('last_name', orm['submit.TempIdAuthors:last_name']),
            ('email_address', orm['submit.TempIdAuthors:email_address']),
            ('last_modified_date', orm['submit.TempIdAuthors:last_modified_date']),
            ('last_modified_time', orm['submit.TempIdAuthors:last_modified_time']),
            ('author_order', orm['submit.TempIdAuthors:author_order']),
            ('submission', orm['submit.TempIdAuthors:submission']),
        ))
        db.send_create_signal('submit', ['TempIdAuthors'])
        
        # Adding model 'IdApprovedDetail'
        db.create_table('id_approved_detail', (
            ('id', orm['submit.IdApprovedDetail:id']),
            ('filename', orm['submit.IdApprovedDetail:filename']),
            ('approved_status', orm['submit.IdApprovedDetail:approved_status']),
            ('approved_person_tag', orm['submit.IdApprovedDetail:approved_person_tag']),
            ('approved_date', orm['submit.IdApprovedDetail:approved_date']),
            ('recorded_by', orm['submit.IdApprovedDetail:recorded_by']),
        ))
        db.send_create_signal('submit', ['IdApprovedDetail'])
        
        # Adding model 'IdSubmissionStatus'
        db.create_table('id_submission_status', (
            ('status_id', orm['submit.IdSubmissionStatus:status_id']),
            ('status_value', orm['submit.IdSubmissionStatus:status_value']),
        ))
        db.send_create_signal('submit', ['IdSubmissionStatus'])
        
        # Adding model 'IdSubmissionDetail'
        db.create_table('id_submission_detail', (
            ('submission_id', orm['submit.IdSubmissionDetail:submission_id']),
            ('temp_id_document_tag', orm['submit.IdSubmissionDetail:temp_id_document_tag']),
            ('status', orm['submit.IdSubmissionDetail:status']),
            ('last_updated_date', orm['submit.IdSubmissionDetail:last_updated_date']),
            ('last_updated_time', orm['submit.IdSubmissionDetail:last_updated_time']),
            ('id_document_name', orm['submit.IdSubmissionDetail:id_document_name']),
            ('group_acronym', orm['submit.IdSubmissionDetail:group_acronym']),
            ('filename', orm['submit.IdSubmissionDetail:filename']),
            ('creation_date', orm['submit.IdSubmissionDetail:creation_date']),
            ('submission_date', orm['submit.IdSubmissionDetail:submission_date']),
            ('remote_ip', orm['submit.IdSubmissionDetail:remote_ip']),
            ('revision', orm['submit.IdSubmissionDetail:revision']),
            ('submitter_tag', orm['submit.IdSubmissionDetail:submitter_tag']),
            ('auth_key', orm['submit.IdSubmissionDetail:auth_key']),
            ('idnits_message', orm['submit.IdSubmissionDetail:idnits_message']),
            ('file_type', orm['submit.IdSubmissionDetail:file_type']),
            ('comment_to_sec', orm['submit.IdSubmissionDetail:comment_to_sec']),
            ('abstract', orm['submit.IdSubmissionDetail:abstract']),
            ('txt_page_count', orm['submit.IdSubmissionDetail:txt_page_count']),
            ('error_message', orm['submit.IdSubmissionDetail:error_message']),
            ('warning_message', orm['submit.IdSubmissionDetail:warning_message']),
            ('wg_submission', orm['submit.IdSubmissionDetail:wg_submission']),
            ('filesize', orm['submit.IdSubmissionDetail:filesize']),
            ('man_posted_date', orm['submit.IdSubmissionDetail:man_posted_date']),
            ('man_posted_by', orm['submit.IdSubmissionDetail:man_posted_by']),
            ('first_two_pages', orm['submit.IdSubmissionDetail:first_two_pages']),
            ('sub_email_priority', orm['submit.IdSubmissionDetail:sub_email_priority']),
            ('invalid_version', orm['submit.IdSubmissionDetail:invalid_version']),
            ('idnits_failed', orm['submit.IdSubmissionDetail:idnits_failed']),
        ))
        db.send_create_signal('submit', ['IdSubmissionDetail'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'TempIdAuthors'
        db.delete_table('temp_id_authors')
        
        # Deleting model 'IdApprovedDetail'
        db.delete_table('id_approved_detail')
        
        # Deleting model 'IdSubmissionStatus'
        db.delete_table('id_submission_status')
        
        # Deleting model 'IdSubmissionDetail'
        db.delete_table('id_submission_detail')
        
    
    
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
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['submit.IdSubmissionDetail']"})
        }
    }
    
    complete_apps = ['submit']
