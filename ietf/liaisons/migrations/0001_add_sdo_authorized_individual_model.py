
from south.db import db
from django.db import models
from ietf.liaisons.models import *


class Migration:

    def forwards(self, orm):

        # Adding model 'SDOAuthorizedIndividual'
        db.create_table('liaisons_sdoauthorizedindividual', (
            ('id', orm['liaisons.SDOAuthorizedIndividual:id']),
            ('person', orm['liaisons.SDOAuthorizedIndividual:person']),
            ('sdo', orm['liaisons.SDOAuthorizedIndividual:sdo']),
        ))
        db.send_create_signal('liaisons', ['SDOAuthorizedIndividual'])

    def backwards(self, orm):

        # Deleting model 'SDOAuthorizedIndividual'
        db.delete_table('liaisons_sdoauthorizedindividual')

    models = {
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
            'record_type': ('django.db.models.fields.CharField', [], {'max_length': '8', 'null': 'True', 'blank': 'True'}),
        },
        'liaisons.frombodies': {
            'Meta': {'db_table': "'from_bodies'"},
            'body_name': ('django.db.models.fields.CharField', [], {'max_length': '35', 'blank': 'True'}),
            'email_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'from_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_liaison_manager': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'other_sdo': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'poc': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'null': 'True', 'db_column': "'poc'"})
        },
        'liaisons.liaisondetail': {
            'Meta': {'db_table': "'liaison_detail'"},
            'body': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'by_secretariat': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'cc1': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cc2': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'deadline_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'detail_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'from_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'last_modified_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'null': 'True', 'db_column': "'person_or_org_tag'"}),
            'purpose': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['liaisons.LiaisonPurpose']", 'null': 'True'}),
            'purpose_text': ('django.db.models.fields.TextField', [], {'null': 'True', 'db_column': "'purpose'", 'blank': 'True'}),
            'replyto': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'response_contact': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'submitted_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'submitter_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'submitter_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'technical_contact': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'to_body': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'to_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'to_poc': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        'liaisons.liaisonmanagers': {
            'Meta': {'db_table': "'liaison_managers'"},
            'email_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'sdo': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['liaisons.SDOs']"})
        },
        'liaisons.liaisonpurpose': {
            'Meta': {'db_table': "'liaison_purpose'"},
            'purpose_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'purpose_text': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        'liaisons.sdoauthorizedindividual': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"}),
            'sdo': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['liaisons.SDOs']"})
        },
        'liaisons.sdos': {
            'Meta': {'db_table': "'sdos'"},
            'sdo_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sdo_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        'liaisons.uploads': {
            'Meta': {'db_table': "'uploads'"},
            'detail': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['liaisons.LiaisonDetail']"}),
            'file_extension': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'}),
            'file_id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'file_title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['idtracker.PersonOrOrgInfo']", 'db_column': "'person_or_org_tag'"})
        }
    }

    complete_apps = ['liaisons']
