
from south.db import db
from django.db import models
from ietf.idtracker.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding field 'InternetDraft.shepherd'
        db.add_column('internet_drafts', 'shepherd', orm['idtracker.internetdraft:shepherd'])
        
    
    
    def backwards(self, orm):
        
        # Deleting field 'InternetDraft.shepherd'
        db.delete_column('internet_drafts', 'shepherd_id')
        
    
    
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
        'idtracker.areagroup': {
            'Meta': {'db_table': "'area_group'"},
            'area': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'areagroup'", 'db_column': "'area_acronym_id'", 'to': "orm['idtracker.Area']"}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']", 'unique': 'True', 'db_column': "'group_acronym_id'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.areastatus': {
            'Meta': {'db_table': "'area_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.areawgurl': {
            'Meta': {'db_table': "'wg_www_pages'"},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True', 'db_column': "'area_ID'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_column': "'area_Name'"}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'idtracker.ballotinfo': {
            'Meta': {'db_table': "'ballot_info'"},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'an_sent': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'an_sent_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ansent'", 'null': 'True', 'db_column': "'an_sent_by'", 'to': "orm['idtracker.IESGLogin']"}),
            'an_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'approval_text': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ballot': ('django.db.models.fields.AutoField', [], {'primary_key': 'True', 'db_column': "'ballot_id'"}),
            'ballot_issued': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'ballot_writeup': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'defer': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'defer_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deferred'", 'null': 'True', 'db_column': "'defer_by'", 'to': "orm['idtracker.IESGLogin']"}),
            'defer_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'last_call_text': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'idtracker.chairshistory': {
            'Meta': {'db_table': "'chairs_history'"},
            'chair_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.Role']"}),
            'end_year': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'present_chair': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'start_year': ('django.db.models.fields.IntegerField', [], {})
        },
        'idtracker.documentcomment': {
            'Meta': {'db_table': "'document_comments'"},
            'ballot': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'comment_text': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created_by': ('BrokenForeignKey', ["orm['idtracker.IESGLogin']"], {'null': 'True', 'db_column': "'created_by'", 'null_values': '(0,999)'}),
            'date': ('django.db.models.fields.DateField', [], {'default': 'datetime.date.today', 'db_column': "'comment_date'"}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IDInternal']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'origin_state': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments_coming_from_state'", 'null': 'True', 'db_column': "'origin_state'", 'to': "orm['idtracker.IDState']"}),
            'public_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'result_state': ('BrokenForeignKey', ["orm['idtracker.IDState']"], {'related_name': '"comments_leading_to_state"', 'null': 'True', 'db_column': "'result_state'", 'null_values': '(0,99)'}),
            'rfc_flag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.CharField', [], {'default': "'05:10:39'", 'max_length': '20', 'db_column': "'comment_time'"}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '3', 'blank': 'True'})
        },
        'idtracker.emailaddress': {
            'Meta': {'db_table': "'email_addresses'"},
            'address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'email_address'"}),
            'comment': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_column': "'email_comment'", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person_or_org': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'priority': ('django.db.models.fields.IntegerField', [], {'db_column': "'email_priority'"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '4', 'db_column': "'email_type'"})
        },
        'idtracker.goalmilestone': {
            'Meta': {'db_table': "'goals_milestones'"},
            'description': ('django.db.models.fields.TextField', [], {}),
            'done': ('django.db.models.fields.CharField', [], {'max_length': '4', 'blank': 'True'}),
            'done_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'expected_due_date': ('django.db.models.fields.DateField', [], {}),
            'gm_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {})
        },
        'idtracker.idauthor': {
            'Meta': {'db_table': "'id_authors'"},
            'author_order': ('django.db.models.fields.IntegerField', [], {}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'authors'", 'db_column': "'id_document_tag'", 'to': "orm['idtracker.InternetDraft']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.idintendedstatus': {
            'Meta': {'db_table': "'id_intended_status'"},
            'intended_status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'intended_status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.idinternal': {
            'Meta': {'db_table': "'id_internal'"},
            'agenda': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'approved_in_minute': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'area_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.Area']"}),
            'assigned_to': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'ballot': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'drafts'", 'db_column': "'ballot_id'", 'to': "orm['idtracker.BallotInfo']"}),
            'cur_state': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'docs'", 'db_column': "'cur_state'", 'to': "orm['idtracker.IDState']"}),
            'cur_sub_state': ('BrokenForeignKey', ["orm['idtracker.IDSubState']"], {'related_name': "'docs'", 'null': 'True', 'null_values': '(0,-1)', 'blank': 'True'}),
            'dnp': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'dnp_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'draft': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.InternetDraft']", 'unique': 'True', 'primary_key': 'True', 'db_column': "'id_document_tag'"}),
            'email_display': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'event_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'group_flag': ('django.db.models.fields.IntegerField', [], {'default': '0', 'blank': 'True'}),
            'job_owner': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'documents'", 'db_column': "'job_owner'", 'to': "orm['idtracker.IESGLogin']"}),
            'mark_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'marked'", 'db_column': "'mark_by'", 'to': "orm['idtracker.IESGLogin']"}),
            'noproblem': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'note': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'prev_state': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'docs_prev'", 'db_column': "'prev_state'", 'to': "orm['idtracker.IDState']"}),
            'prev_sub_state': ('BrokenForeignKey', ["orm['idtracker.IDSubState']"], {'related_name': "'docs_prev'", 'null': 'True', 'null_values': '(0,-1)', 'blank': 'True'}),
            'primary_flag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'resurrect_requested_by': ('BrokenForeignKey', ["orm['idtracker.IESGLogin']"], {'related_name': "'docsresurrected'", 'null': 'True', 'db_column': "'resurrect_requested_by'", 'blank': 'True'}),
            'returning_item': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rfc_flag': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'state_change_notice_to': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'status_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'telechat_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'token_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'token_name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'via_rfc_editor': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'idtracker.idnextstate': {
            'Meta': {'db_table': "'ref_next_states_new'"},
            'condition': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'cur_state': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'nextstate'", 'to': "orm['idtracker.IDState']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'next_state': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'prevstate'", 'to': "orm['idtracker.IDState']"})
        },
        'idtracker.idstate': {
            'Meta': {'db_table': "'ref_doc_states_new'"},
            'description': ('django.db.models.fields.TextField', [], {'db_column': "'document_desc'", 'blank': 'True'}),
            'document_state_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'equiv_group_flag': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_column': "'document_state_val'"})
        },
        'idtracker.idstatus': {
            'Meta': {'db_table': "'id_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.idsubstate': {
            'Meta': {'db_table': "'sub_state'"},
            'description': ('django.db.models.fields.TextField', [], {'db_column': "'sub_state_desc'", 'blank': 'True'}),
            'sub_state': ('django.db.models.fields.CharField', [], {'max_length': '55', 'db_column': "'sub_state_val'"}),
            'sub_state_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.iesgcomment': {
            'Meta': {'unique_together': "(('ballot', 'ad'),)", 'db_table': "'ballots_comment'"},
            'active': ('django.db.models.fields.IntegerField', [], {}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IESGLogin']"}),
            'ballot': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': "orm['idtracker.BallotInfo']"}),
            'date': ('django.db.models.fields.DateField', [], {'db_column': "'comment_date'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'revision': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'text': ('django.db.models.fields.TextField', [], {'db_column': "'comment_text'", 'blank': 'True'})
        },
        'idtracker.iesgdiscuss': {
            'Meta': {'unique_together': "(('ballot', 'ad'),)", 'db_table': "'ballots_discuss'"},
            'active': ('django.db.models.fields.IntegerField', [], {}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IESGLogin']"}),
            'ballot': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'discusses'", 'to': "orm['idtracker.BallotInfo']"}),
            'date': ('django.db.models.fields.DateField', [], {'db_column': "'discuss_date'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'revision': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'text': ('django.db.models.fields.TextField', [], {'db_column': "'discuss_text'", 'blank': 'True'})
        },
        'idtracker.iesglogin': {
            'Meta': {'db_table': "'iesg_login'"},
            'default_search': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'login_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '25'}),
            'person': ('BrokenForeignKey', ["orm['idtracker.PersonOrOrgInfo']"], {'unique': 'True', 'null': 'True', 'db_column': "'person_or_org_tag'", 'null_values': '(0,888888)'}),
            'pgp_id': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'user_level': ('django.db.models.fields.IntegerField', [], {})
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
            'replaced_by': ('BrokenForeignKey', ["orm['idtracker.InternetDraft']"], {'related_name': "'replaces_set'", 'null': 'True', 'db_column': "'replaced_by'", 'blank': 'True'}),
            'review_by_rfc_editor': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'revision': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'revision_date': ('django.db.models.fields.DateField', [], {}),
            'rfc_number': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'shepherd': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']"}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IDStatus']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'id_document_name'"}),
            'txt_page_count': ('django.db.models.fields.IntegerField', [], {}),
            'wgreturn_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        'idtracker.irtf': {
            'Meta': {'db_table': "'irtf'"},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'irtf_acronym'", 'blank': 'True'}),
            'charter_text': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'irtf_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meeting_scheduled': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_column': "'irtf_name'", 'blank': 'True'})
        },
        'idtracker.irtfchair': {
            'Meta': {'db_table': "'irtf_chairs'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'irtf': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IRTF']"}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
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
        'idtracker.phonenumber': {
            'Meta': {'db_table': "'phone_numbers'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person_or_org': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'phone_comment': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'phone_priority': ('django.db.models.fields.IntegerField', [], {}),
            'phone_type': ('django.db.models.fields.CharField', [], {'max_length': '3'})
        },
        'idtracker.position': {
            'Meta': {'unique_together': "(('ballot', 'ad'),)", 'db_table': "'ballots'"},
            'abstain': ('django.db.models.fields.IntegerField', [], {}),
            'ad': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IESGLogin']"}),
            'approve': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'ballot': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'positions'", 'to': "orm['idtracker.BallotInfo']"}),
            'discuss': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'noobj': ('django.db.models.fields.IntegerField', [], {'db_column': "'no_col'"}),
            'recuse': ('django.db.models.fields.IntegerField', [], {}),
            'yes': ('django.db.models.fields.IntegerField', [], {'db_column': "'yes_col'"})
        },
        'idtracker.postaladdress': {
            'Meta': {'db_table': "'postal_addresses'"},
            'address_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'address_type': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'aff_company_key': ('django.db.models.fields.CharField', [], {'max_length': '70', 'blank': 'True'}),
            'affiliated_company': ('django.db.models.fields.CharField', [], {'max_length': '70', 'blank': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'department': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mail_stop': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'person_or_org': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'person_title': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'staddr1': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'staddr2': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'}),
            'state_or_prov': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'})
        },
        'idtracker.rfc': {
            'Meta': {'db_table': "'rfcs'"},
            'area_acronym': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'b_approve_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'b_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'draft_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'fyi_number': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'group_acronym': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'historic_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'intended_status': ('django.db.models.fields.related.ForeignKey', [], {'default': '5', 'to': "orm['idtracker.RfcIntendedStatus']", 'db_column': "'intended_status_id'"}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {}),
            'lc_expiration_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'lc_sent_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'online_version': ('django.db.models.fields.CharField', [], {'default': "'YES'", 'max_length': '3'}),
            'proposed_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'rfc_name_key': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'rfc_number': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'rfc_published_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'standard_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.RfcStatus']", 'db_column': "'status_id'"}),
            'std_number': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_column': "'rfc_name'"}),
            'txt_page_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'idtracker.rfcauthor': {
            'Meta': {'db_table': "'rfc_authors'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'rfc': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'authors'", 'db_column': "'rfc_number'", 'to': "orm['idtracker.Rfc']"})
        },
        'idtracker.rfcintendedstatus': {
            'Meta': {'db_table': "'rfc_intend_status'"},
            'intended_status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"})
        },
        'idtracker.rfcobsolete': {
            'Meta': {'db_table': "'rfcs_obsolete'"},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rfc': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updates_or_obsoletes'", 'db_column': "'rfc_number'", 'to': "orm['idtracker.Rfc']"}),
            'rfc_acted_on': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'updated_or_obsoleted_by'", 'db_column': "'rfc_acted_on'", 'to': "orm['idtracker.Rfc']"})
        },
        'idtracker.rfcstatus': {
            'Meta': {'db_table': "'rfc_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.role': {
            'Meta': {'db_table': "'chairs'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'role_name': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'chair_name'"})
        },
        'idtracker.wgchair': {
            'Meta': {'db_table': "'g_chairs'"},
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.wgeditor': {
            'Meta': {'db_table': "'g_editors'"},
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'unique': 'True', 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.wgsecretary': {
            'Meta': {'db_table': "'g_secretaries'"},
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.wgstatus': {
            'Meta': {'db_table': "'g_status'"},
            'status': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'status_value'"}),
            'status_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'idtracker.wgtechadvisor': {
            'Meta': {'db_table': "'g_tech_advisors'"},
            'group_acronym': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.IETFWG']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        },
        'idtracker.wgtype': {
            'Meta': {'db_table': "'g_type'"},
            'group_type_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '25', 'db_column': "'group_type'"})
        }
    }
    
    complete_apps = ['idtracker']
