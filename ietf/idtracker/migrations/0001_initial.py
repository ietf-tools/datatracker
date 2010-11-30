
from south.db import db
from django.db import models
from ietf.idtracker.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'WGTechAdvisor'
        db.create_table('g_tech_advisors', (
            ('id', orm['idtracker.WGTechAdvisor:id']),
            ('group_acronym', orm['idtracker.WGTechAdvisor:group_acronym']),
            ('person', orm['idtracker.WGTechAdvisor:person']),
        ))
        db.send_create_signal('idtracker', ['WGTechAdvisor'])
        
        # Adding model 'IDState'
        db.create_table('ref_doc_states_new', (
            ('document_state_id', orm['idtracker.IDState:document_state_id']),
            ('state', orm['idtracker.IDState:state']),
            ('equiv_group_flag', orm['idtracker.IDState:equiv_group_flag']),
            ('description', orm['idtracker.IDState:description']),
        ))
        db.send_create_signal('idtracker', ['IDState'])
        
        # Adding model 'BallotInfo'
        db.create_table('ballot_info', (
            ('ballot', orm['idtracker.BallotInfo:ballot']),
            ('active', orm['idtracker.BallotInfo:active']),
            ('an_sent', orm['idtracker.BallotInfo:an_sent']),
            ('an_sent_date', orm['idtracker.BallotInfo:an_sent_date']),
            ('an_sent_by', orm['idtracker.BallotInfo:an_sent_by']),
            ('defer', orm['idtracker.BallotInfo:defer']),
            ('defer_by', orm['idtracker.BallotInfo:defer_by']),
            ('defer_date', orm['idtracker.BallotInfo:defer_date']),
            ('approval_text', orm['idtracker.BallotInfo:approval_text']),
            ('last_call_text', orm['idtracker.BallotInfo:last_call_text']),
            ('ballot_writeup', orm['idtracker.BallotInfo:ballot_writeup']),
            ('ballot_issued', orm['idtracker.BallotInfo:ballot_issued']),
        ))
        db.send_create_signal('idtracker', ['BallotInfo'])
        
        # Adding model 'AreaStatus'
        db.create_table('area_status', (
            ('status_id', orm['idtracker.AreaStatus:status_id']),
            ('status', orm['idtracker.AreaStatus:status']),
        ))
        db.send_create_signal('idtracker', ['AreaStatus'])
        
        # Adding model 'RfcAuthor'
        db.create_table('rfc_authors', (
            ('id', orm['idtracker.RfcAuthor:id']),
            ('rfc', orm['idtracker.RfcAuthor:rfc']),
            ('person', orm['idtracker.RfcAuthor:person']),
        ))
        db.send_create_signal('idtracker', ['RfcAuthor'])
        
        # Adding model 'IDIntendedStatus'
        db.create_table('id_intended_status', (
            ('intended_status_id', orm['idtracker.IDIntendedStatus:intended_status_id']),
            ('intended_status', orm['idtracker.IDIntendedStatus:intended_status']),
        ))
        db.send_create_signal('idtracker', ['IDIntendedStatus'])
        
        # Adding model 'IDNextState'
        db.create_table('ref_next_states_new', (
            ('id', orm['idtracker.IDNextState:id']),
            ('cur_state', orm['idtracker.IDNextState:cur_state']),
            ('next_state', orm['idtracker.IDNextState:next_state']),
            ('condition', orm['idtracker.IDNextState:condition']),
        ))
        db.send_create_signal('idtracker', ['IDNextState'])
        
        # Adding model 'WGType'
        db.create_table('g_type', (
            ('group_type_id', orm['idtracker.WGType:group_type_id']),
            ('type', orm['idtracker.WGType:type']),
        ))
        db.send_create_signal('idtracker', ['WGType'])
        
        # Adding model 'RfcObsolete'
        db.create_table('rfcs_obsolete', (
            ('id', orm['idtracker.RfcObsolete:id']),
            ('rfc', orm['idtracker.RfcObsolete:rfc']),
            ('action', orm['idtracker.RfcObsolete:action']),
            ('rfc_acted_on', orm['idtracker.RfcObsolete:rfc_acted_on']),
        ))
        db.send_create_signal('idtracker', ['RfcObsolete'])
        
        # Adding model 'InternetDraft'
        db.create_table('internet_drafts', (
            ('id_document_tag', orm['idtracker.InternetDraft:id_document_tag']),
            ('title', orm['idtracker.InternetDraft:title']),
            ('id_document_key', orm['idtracker.InternetDraft:id_document_key']),
            ('group', orm['idtracker.InternetDraft:group']),
            ('filename', orm['idtracker.InternetDraft:filename']),
            ('revision', orm['idtracker.InternetDraft:revision']),
            ('revision_date', orm['idtracker.InternetDraft:revision_date']),
            ('file_type', orm['idtracker.InternetDraft:file_type']),
            ('txt_page_count', orm['idtracker.InternetDraft:txt_page_count']),
            ('local_path', orm['idtracker.InternetDraft:local_path']),
            ('start_date', orm['idtracker.InternetDraft:start_date']),
            ('expiration_date', orm['idtracker.InternetDraft:expiration_date']),
            ('abstract', orm['idtracker.InternetDraft:abstract']),
            ('dunn_sent_date', orm['idtracker.InternetDraft:dunn_sent_date']),
            ('extension_date', orm['idtracker.InternetDraft:extension_date']),
            ('status', orm['idtracker.InternetDraft:status']),
            ('intended_status', orm['idtracker.InternetDraft:intended_status']),
            ('lc_sent_date', orm['idtracker.InternetDraft:lc_sent_date']),
            ('lc_changes', orm['idtracker.InternetDraft:lc_changes']),
            ('lc_expiration_date', orm['idtracker.InternetDraft:lc_expiration_date']),
            ('b_sent_date', orm['idtracker.InternetDraft:b_sent_date']),
            ('b_discussion_date', orm['idtracker.InternetDraft:b_discussion_date']),
            ('b_approve_date', orm['idtracker.InternetDraft:b_approve_date']),
            ('wgreturn_date', orm['idtracker.InternetDraft:wgreturn_date']),
            ('rfc_number', orm['idtracker.InternetDraft:rfc_number']),
            ('comments', orm['idtracker.InternetDraft:comments']),
            ('last_modified_date', orm['idtracker.InternetDraft:last_modified_date']),
            ('replaced_by', orm['idtracker.InternetDraft:replaced_by']),
            ('review_by_rfc_editor', orm['idtracker.InternetDraft:review_by_rfc_editor']),
            ('expired_tombstone', orm['idtracker.InternetDraft:expired_tombstone']),
        ))
        db.send_create_signal('idtracker', ['InternetDraft'])
        
        # Adding model 'IRTFChair'
        db.create_table('irtf_chairs', (
            ('id', orm['idtracker.IRTFChair:id']),
            ('irtf', orm['idtracker.IRTFChair:irtf']),
            ('person', orm['idtracker.IRTFChair:person']),
        ))
        db.send_create_signal('idtracker', ['IRTFChair'])
        
        # Adding model 'IETFWG'
        db.create_table('groups_ietf', (
            ('group_acronym', orm['idtracker.IETFWG:group_acronym']),
            ('group_type', orm['idtracker.IETFWG:group_type']),
            ('proposed_date', orm['idtracker.IETFWG:proposed_date']),
            ('start_date', orm['idtracker.IETFWG:start_date']),
            ('dormant_date', orm['idtracker.IETFWG:dormant_date']),
            ('concluded_date', orm['idtracker.IETFWG:concluded_date']),
            ('status', orm['idtracker.IETFWG:status']),
            ('area_director', orm['idtracker.IETFWG:area_director']),
            ('meeting_scheduled', orm['idtracker.IETFWG:meeting_scheduled']),
            ('email_address', orm['idtracker.IETFWG:email_address']),
            ('email_subscribe', orm['idtracker.IETFWG:email_subscribe']),
            ('email_keyword', orm['idtracker.IETFWG:email_keyword']),
            ('email_archive', orm['idtracker.IETFWG:email_archive']),
            ('comments', orm['idtracker.IETFWG:comments']),
            ('last_modified_date', orm['idtracker.IETFWG:last_modified_date']),
            ('meeting_scheduled_old', orm['idtracker.IETFWG:meeting_scheduled_old']),
        ))
        db.send_create_signal('idtracker', ['IETFWG'])
        
        # Adding model 'PostalAddress'
        db.create_table('postal_addresses', (
            ('id', orm['idtracker.PostalAddress:id']),
            ('address_type', orm['idtracker.PostalAddress:address_type']),
            ('address_priority', orm['idtracker.PostalAddress:address_priority']),
            ('person_or_org', orm['idtracker.PostalAddress:person_or_org']),
            ('person_title', orm['idtracker.PostalAddress:person_title']),
            ('affiliated_company', orm['idtracker.PostalAddress:affiliated_company']),
            ('aff_company_key', orm['idtracker.PostalAddress:aff_company_key']),
            ('department', orm['idtracker.PostalAddress:department']),
            ('staddr1', orm['idtracker.PostalAddress:staddr1']),
            ('staddr2', orm['idtracker.PostalAddress:staddr2']),
            ('mail_stop', orm['idtracker.PostalAddress:mail_stop']),
            ('city', orm['idtracker.PostalAddress:city']),
            ('state_or_prov', orm['idtracker.PostalAddress:state_or_prov']),
            ('postal_code', orm['idtracker.PostalAddress:postal_code']),
            ('country', orm['idtracker.PostalAddress:country']),
        ))
        db.send_create_signal('idtracker', ['PostalAddress'])
        
        # Adding model 'RfcIntendedStatus'
        db.create_table('rfc_intend_status', (
            ('intended_status_id', orm['idtracker.RfcIntendedStatus:intended_status_id']),
            ('status', orm['idtracker.RfcIntendedStatus:status']),
        ))
        db.send_create_signal('idtracker', ['RfcIntendedStatus'])
        
        # Adding model 'IDInternal'
        db.create_table('id_internal', (
            ('draft', orm['idtracker.IDInternal:draft']),
            ('rfc_flag', orm['idtracker.IDInternal:rfc_flag']),
            ('ballot', orm['idtracker.IDInternal:ballot']),
            ('primary_flag', orm['idtracker.IDInternal:primary_flag']),
            ('group_flag', orm['idtracker.IDInternal:group_flag']),
            ('token_name', orm['idtracker.IDInternal:token_name']),
            ('token_email', orm['idtracker.IDInternal:token_email']),
            ('note', orm['idtracker.IDInternal:note']),
            ('status_date', orm['idtracker.IDInternal:status_date']),
            ('email_display', orm['idtracker.IDInternal:email_display']),
            ('agenda', orm['idtracker.IDInternal:agenda']),
            ('cur_state', orm['idtracker.IDInternal:cur_state']),
            ('prev_state', orm['idtracker.IDInternal:prev_state']),
            ('assigned_to', orm['idtracker.IDInternal:assigned_to']),
            ('mark_by', orm['idtracker.IDInternal:mark_by']),
            ('job_owner', orm['idtracker.IDInternal:job_owner']),
            ('event_date', orm['idtracker.IDInternal:event_date']),
            ('area_acronym', orm['idtracker.IDInternal:area_acronym']),
            ('cur_sub_state', orm['idtracker.IDInternal:cur_sub_state']),
            ('prev_sub_state', orm['idtracker.IDInternal:prev_sub_state']),
            ('returning_item', orm['idtracker.IDInternal:returning_item']),
            ('telechat_date', orm['idtracker.IDInternal:telechat_date']),
            ('via_rfc_editor', orm['idtracker.IDInternal:via_rfc_editor']),
            ('state_change_notice_to', orm['idtracker.IDInternal:state_change_notice_to']),
            ('dnp', orm['idtracker.IDInternal:dnp']),
            ('dnp_date', orm['idtracker.IDInternal:dnp_date']),
            ('noproblem', orm['idtracker.IDInternal:noproblem']),
            ('resurrect_requested_by', orm['idtracker.IDInternal:resurrect_requested_by']),
            ('approved_in_minute', orm['idtracker.IDInternal:approved_in_minute']),
        ))
        db.send_create_signal('idtracker', ['IDInternal'])
        
        # Adding model 'IDAuthor'
        db.create_table('id_authors', (
            ('id', orm['idtracker.IDAuthor:id']),
            ('document', orm['idtracker.IDAuthor:document']),
            ('person', orm['idtracker.IDAuthor:person']),
            ('author_order', orm['idtracker.IDAuthor:author_order']),
        ))
        db.send_create_signal('idtracker', ['IDAuthor'])
        
        # Adding model 'IDStatus'
        db.create_table('id_status', (
            ('status_id', orm['idtracker.IDStatus:status_id']),
            ('status', orm['idtracker.IDStatus:status']),
        ))
        db.send_create_signal('idtracker', ['IDStatus'])
        
        # Adding model 'Role'
        db.create_table('chairs', (
            ('id', orm['idtracker.Role:id']),
            ('person', orm['idtracker.Role:person']),
            ('role_name', orm['idtracker.Role:role_name']),
        ))
        db.send_create_signal('idtracker', ['Role'])
        
        # Adding model 'AreaDirector'
        db.create_table('area_directors', (
            ('id', orm['idtracker.AreaDirector:id']),
            ('area', orm['idtracker.AreaDirector:area']),
            ('person', orm['idtracker.AreaDirector:person']),
        ))
        db.send_create_signal('idtracker', ['AreaDirector'])
        
        # Adding model 'Rfc'
        db.create_table('rfcs', (
            ('rfc_number', orm['idtracker.Rfc:rfc_number']),
            ('title', orm['idtracker.Rfc:title']),
            ('rfc_name_key', orm['idtracker.Rfc:rfc_name_key']),
            ('group_acronym', orm['idtracker.Rfc:group_acronym']),
            ('area_acronym', orm['idtracker.Rfc:area_acronym']),
            ('status', orm['idtracker.Rfc:status']),
            ('intended_status', orm['idtracker.Rfc:intended_status']),
            ('fyi_number', orm['idtracker.Rfc:fyi_number']),
            ('std_number', orm['idtracker.Rfc:std_number']),
            ('txt_page_count', orm['idtracker.Rfc:txt_page_count']),
            ('online_version', orm['idtracker.Rfc:online_version']),
            ('rfc_published_date', orm['idtracker.Rfc:rfc_published_date']),
            ('proposed_date', orm['idtracker.Rfc:proposed_date']),
            ('draft_date', orm['idtracker.Rfc:draft_date']),
            ('standard_date', orm['idtracker.Rfc:standard_date']),
            ('historic_date', orm['idtracker.Rfc:historic_date']),
            ('lc_sent_date', orm['idtracker.Rfc:lc_sent_date']),
            ('lc_expiration_date', orm['idtracker.Rfc:lc_expiration_date']),
            ('b_sent_date', orm['idtracker.Rfc:b_sent_date']),
            ('b_approve_date', orm['idtracker.Rfc:b_approve_date']),
            ('comments', orm['idtracker.Rfc:comments']),
            ('last_modified_date', orm['idtracker.Rfc:last_modified_date']),
        ))
        db.send_create_signal('idtracker', ['Rfc'])
        
        # Adding model 'EmailAddress'
        db.create_table('email_addresses', (
            ('id', orm['idtracker.EmailAddress:id']),
            ('person_or_org', orm['idtracker.EmailAddress:person_or_org']),
            ('type', orm['idtracker.EmailAddress:type']),
            ('priority', orm['idtracker.EmailAddress:priority']),
            ('address', orm['idtracker.EmailAddress:address']),
            ('comment', orm['idtracker.EmailAddress:comment']),
        ))
        db.send_create_signal('idtracker', ['EmailAddress'])
        
        # Adding model 'AreaGroup'
        db.create_table('area_group', (
            ('id', orm['idtracker.AreaGroup:id']),
            ('area', orm['idtracker.AreaGroup:area']),
            ('group', orm['idtracker.AreaGroup:group']),
        ))
        db.send_create_signal('idtracker', ['AreaGroup'])
        
        # Adding model 'IESGDiscuss'
        db.create_table('ballots_discuss', (
            ('id', orm['idtracker.IESGDiscuss:id']),
            ('ballot', orm['idtracker.IESGDiscuss:ballot']),
            ('ad', orm['idtracker.IESGDiscuss:ad']),
            ('date', orm['idtracker.IESGDiscuss:date']),
            ('revision', orm['idtracker.IESGDiscuss:revision']),
            ('active', orm['idtracker.IESGDiscuss:active']),
            ('text', orm['idtracker.IESGDiscuss:text']),
        ))
        db.send_create_signal('idtracker', ['IESGDiscuss'])
        
        # Adding model 'GoalMilestone'
        db.create_table('goals_milestones', (
            ('gm_id', orm['idtracker.GoalMilestone:gm_id']),
            ('group_acronym', orm['idtracker.GoalMilestone:group_acronym']),
            ('description', orm['idtracker.GoalMilestone:description']),
            ('expected_due_date', orm['idtracker.GoalMilestone:expected_due_date']),
            ('done_date', orm['idtracker.GoalMilestone:done_date']),
            ('done', orm['idtracker.GoalMilestone:done']),
            ('last_modified_date', orm['idtracker.GoalMilestone:last_modified_date']),
        ))
        db.send_create_signal('idtracker', ['GoalMilestone'])
        
        # Adding model 'PhoneNumber'
        db.create_table('phone_numbers', (
            ('id', orm['idtracker.PhoneNumber:id']),
            ('person_or_org', orm['idtracker.PhoneNumber:person_or_org']),
            ('phone_type', orm['idtracker.PhoneNumber:phone_type']),
            ('phone_priority', orm['idtracker.PhoneNumber:phone_priority']),
            ('phone_number', orm['idtracker.PhoneNumber:phone_number']),
            ('phone_comment', orm['idtracker.PhoneNumber:phone_comment']),
        ))
        db.send_create_signal('idtracker', ['PhoneNumber'])
        
        # Adding model 'WGSecretary'
        db.create_table('g_secretaries', (
            ('id', orm['idtracker.WGSecretary:id']),
            ('group_acronym', orm['idtracker.WGSecretary:group_acronym']),
            ('person', orm['idtracker.WGSecretary:person']),
        ))
        db.send_create_signal('idtracker', ['WGSecretary'])
        
        # Adding model 'WGStatus'
        db.create_table('g_status', (
            ('status_id', orm['idtracker.WGStatus:status_id']),
            ('status', orm['idtracker.WGStatus:status']),
        ))
        db.send_create_signal('idtracker', ['WGStatus'])
        
        # Adding model 'IRTF'
        db.create_table('irtf', (
            ('irtf_id', orm['idtracker.IRTF:irtf_id']),
            ('acronym', orm['idtracker.IRTF:acronym']),
            ('name', orm['idtracker.IRTF:name']),
            ('charter_text', orm['idtracker.IRTF:charter_text']),
            ('meeting_scheduled', orm['idtracker.IRTF:meeting_scheduled']),
        ))
        db.send_create_signal('idtracker', ['IRTF'])
        
        # Adding model 'RfcStatus'
        db.create_table('rfc_status', (
            ('status_id', orm['idtracker.RfcStatus:status_id']),
            ('status', orm['idtracker.RfcStatus:status']),
        ))
        db.send_create_signal('idtracker', ['RfcStatus'])
        
        # Adding model 'Area'
        db.create_table('areas', (
            ('area_acronym', orm['idtracker.Area:area_acronym']),
            ('start_date', orm['idtracker.Area:start_date']),
            ('concluded_date', orm['idtracker.Area:concluded_date']),
            ('status', orm['idtracker.Area:status']),
            ('comments', orm['idtracker.Area:comments']),
            ('last_modified_date', orm['idtracker.Area:last_modified_date']),
            ('extra_email_addresses', orm['idtracker.Area:extra_email_addresses']),
        ))
        db.send_create_signal('idtracker', ['Area'])
        
        # Adding model 'ChairsHistory'
        db.create_table('chairs_history', (
            ('id', orm['idtracker.ChairsHistory:id']),
            ('chair_type', orm['idtracker.ChairsHistory:chair_type']),
            ('present_chair', orm['idtracker.ChairsHistory:present_chair']),
            ('person', orm['idtracker.ChairsHistory:person']),
            ('start_year', orm['idtracker.ChairsHistory:start_year']),
            ('end_year', orm['idtracker.ChairsHistory:end_year']),
        ))
        db.send_create_signal('idtracker', ['ChairsHistory'])
        
        # Adding model 'Acronym'
        db.create_table('acronym', (
            ('acronym_id', orm['idtracker.Acronym:acronym_id']),
            ('acronym', orm['idtracker.Acronym:acronym']),
            ('name', orm['idtracker.Acronym:name']),
            ('name_key', orm['idtracker.Acronym:name_key']),
        ))
        db.send_create_signal('idtracker', ['Acronym'])
        
        # Adding model 'WGChair'
        db.create_table('g_chairs', (
            ('id', orm['idtracker.WGChair:id']),
            ('person', orm['idtracker.WGChair:person']),
            ('group_acronym', orm['idtracker.WGChair:group_acronym']),
        ))
        db.send_create_signal('idtracker', ['WGChair'])
        
        # Adding model 'WGEditor'
        db.create_table('g_editors', (
            ('id', orm['idtracker.WGEditor:id']),
            ('group_acronym', orm['idtracker.WGEditor:group_acronym']),
            ('person', orm['idtracker.WGEditor:person']),
        ))
        db.send_create_signal('idtracker', ['WGEditor'])
        
        # Adding model 'PersonOrOrgInfo'
        db.create_table('person_or_org_info', (
            ('person_or_org_tag', orm['idtracker.PersonOrOrgInfo:person_or_org_tag']),
            ('record_type', orm['idtracker.PersonOrOrgInfo:record_type']),
            ('name_prefix', orm['idtracker.PersonOrOrgInfo:name_prefix']),
            ('first_name', orm['idtracker.PersonOrOrgInfo:first_name']),
            ('first_name_key', orm['idtracker.PersonOrOrgInfo:first_name_key']),
            ('middle_initial', orm['idtracker.PersonOrOrgInfo:middle_initial']),
            ('middle_initial_key', orm['idtracker.PersonOrOrgInfo:middle_initial_key']),
            ('last_name', orm['idtracker.PersonOrOrgInfo:last_name']),
            ('last_name_key', orm['idtracker.PersonOrOrgInfo:last_name_key']),
            ('name_suffix', orm['idtracker.PersonOrOrgInfo:name_suffix']),
            ('date_modified', orm['idtracker.PersonOrOrgInfo:date_modified']),
            ('modified_by', orm['idtracker.PersonOrOrgInfo:modified_by']),
            ('date_created', orm['idtracker.PersonOrOrgInfo:date_created']),
            ('created_by', orm['idtracker.PersonOrOrgInfo:created_by']),
            ('address_type', orm['idtracker.PersonOrOrgInfo:address_type']),
        ))
        db.send_create_signal('idtracker', ['PersonOrOrgInfo'])
        
        # Adding model 'Position'
        db.create_table('ballots', (
            ('id', orm['idtracker.Position:id']),
            ('ballot', orm['idtracker.Position:ballot']),
            ('ad', orm['idtracker.Position:ad']),
            ('yes', orm['idtracker.Position:yes']),
            ('noobj', orm['idtracker.Position:noobj']),
            ('abstain', orm['idtracker.Position:abstain']),
            ('approve', orm['idtracker.Position:approve']),
            ('discuss', orm['idtracker.Position:discuss']),
            ('recuse', orm['idtracker.Position:recuse']),
        ))
        db.send_create_signal('idtracker', ['Position'])
        
        # Adding model 'IESGComment'
        db.create_table('ballots_comment', (
            ('id', orm['idtracker.IESGComment:id']),
            ('ballot', orm['idtracker.IESGComment:ballot']),
            ('ad', orm['idtracker.IESGComment:ad']),
            ('date', orm['idtracker.IESGComment:date']),
            ('revision', orm['idtracker.IESGComment:revision']),
            ('active', orm['idtracker.IESGComment:active']),
            ('text', orm['idtracker.IESGComment:text']),
        ))
        db.send_create_signal('idtracker', ['IESGComment'])
        
        # Adding model 'IESGLogin'
        db.create_table('iesg_login', (
            ('id', orm['idtracker.IESGLogin:id']),
            ('login_name', orm['idtracker.IESGLogin:login_name']),
            ('password', orm['idtracker.IESGLogin:password']),
            ('user_level', orm['idtracker.IESGLogin:user_level']),
            ('first_name', orm['idtracker.IESGLogin:first_name']),
            ('last_name', orm['idtracker.IESGLogin:last_name']),
            ('person', orm['idtracker.IESGLogin:person']),
            ('pgp_id', orm['idtracker.IESGLogin:pgp_id']),
            ('default_search', orm['idtracker.IESGLogin:default_search']),
        ))
        db.send_create_signal('idtracker', ['IESGLogin'])
        
        # Adding model 'AreaWGURL'
        db.create_table('wg_www_pages', (
            ('id', orm['idtracker.AreaWGURL:id']),
            ('name', orm['idtracker.AreaWGURL:name']),
            ('url', orm['idtracker.AreaWGURL:url']),
            ('description', orm['idtracker.AreaWGURL:description']),
        ))
        db.send_create_signal('idtracker', ['AreaWGURL'])
        
        # Adding model 'IDSubState'
        db.create_table('sub_state', (
            ('sub_state_id', orm['idtracker.IDSubState:sub_state_id']),
            ('sub_state', orm['idtracker.IDSubState:sub_state']),
            ('description', orm['idtracker.IDSubState:description']),
        ))
        db.send_create_signal('idtracker', ['IDSubState'])
        
        # Adding model 'DocumentComment'
        db.create_table('document_comments', (
            ('id', orm['idtracker.DocumentComment:id']),
            ('document', orm['idtracker.DocumentComment:document']),
            ('rfc_flag', orm['idtracker.DocumentComment:rfc_flag']),
            ('public_flag', orm['idtracker.DocumentComment:public_flag']),
            ('date', orm['idtracker.DocumentComment:date']),
            ('time', orm['idtracker.DocumentComment:time']),
            ('version', orm['idtracker.DocumentComment:version']),
            ('comment_text', orm['idtracker.DocumentComment:comment_text']),
            ('created_by', orm['idtracker.DocumentComment:created_by']),
            ('result_state', orm['idtracker.DocumentComment:result_state']),
            ('origin_state', orm['idtracker.DocumentComment:origin_state']),
            ('ballot', orm['idtracker.DocumentComment:ballot']),
        ))
        db.send_create_signal('idtracker', ['DocumentComment'])
        
        # Creating unique_together for [ballot, ad] on IESGDiscuss.
        db.create_unique('ballots_discuss', ['ballot_id', 'ad_id'])
        
        # Creating unique_together for [ballot, ad] on Position.
        db.create_unique('ballots', ['ballot_id', 'ad_id'])
        
        # Creating unique_together for [ballot, ad] on IESGComment.
        db.create_unique('ballots_comment', ['ballot_id', 'ad_id'])
        
    
    
    def backwards(self, orm):
        
        # Deleting unique_together for [ballot, ad] on IESGComment.
        db.delete_unique('ballots_comment', ['ballot_id', 'ad_id'])
        
        # Deleting unique_together for [ballot, ad] on Position.
        db.delete_unique('ballots', ['ballot_id', 'ad_id'])
        
        # Deleting unique_together for [ballot, ad] on IESGDiscuss.
        db.delete_unique('ballots_discuss', ['ballot_id', 'ad_id'])
        
        # Deleting model 'WGTechAdvisor'
        db.delete_table('g_tech_advisors')
        
        # Deleting model 'IDState'
        db.delete_table('ref_doc_states_new')
        
        # Deleting model 'BallotInfo'
        db.delete_table('ballot_info')
        
        # Deleting model 'AreaStatus'
        db.delete_table('area_status')
        
        # Deleting model 'RfcAuthor'
        db.delete_table('rfc_authors')
        
        # Deleting model 'IDIntendedStatus'
        db.delete_table('id_intended_status')
        
        # Deleting model 'IDNextState'
        db.delete_table('ref_next_states_new')
        
        # Deleting model 'WGType'
        db.delete_table('g_type')
        
        # Deleting model 'RfcObsolete'
        db.delete_table('rfcs_obsolete')
        
        # Deleting model 'InternetDraft'
        db.delete_table('internet_drafts')
        
        # Deleting model 'IRTFChair'
        db.delete_table('irtf_chairs')
        
        # Deleting model 'IETFWG'
        db.delete_table('groups_ietf')
        
        # Deleting model 'PostalAddress'
        db.delete_table('postal_addresses')
        
        # Deleting model 'RfcIntendedStatus'
        db.delete_table('rfc_intend_status')
        
        # Deleting model 'IDInternal'
        db.delete_table('id_internal')
        
        # Deleting model 'IDAuthor'
        db.delete_table('id_authors')
        
        # Deleting model 'IDStatus'
        db.delete_table('id_status')
        
        # Deleting model 'Role'
        db.delete_table('chairs')
        
        # Deleting model 'AreaDirector'
        db.delete_table('area_directors')
        
        # Deleting model 'Rfc'
        db.delete_table('rfcs')
        
        # Deleting model 'EmailAddress'
        db.delete_table('email_addresses')
        
        # Deleting model 'AreaGroup'
        db.delete_table('area_group')
        
        # Deleting model 'IESGDiscuss'
        db.delete_table('ballots_discuss')
        
        # Deleting model 'GoalMilestone'
        db.delete_table('goals_milestones')
        
        # Deleting model 'PhoneNumber'
        db.delete_table('phone_numbers')
        
        # Deleting model 'WGSecretary'
        db.delete_table('g_secretaries')
        
        # Deleting model 'WGStatus'
        db.delete_table('g_status')
        
        # Deleting model 'IRTF'
        db.delete_table('irtf')
        
        # Deleting model 'RfcStatus'
        db.delete_table('rfc_status')
        
        # Deleting model 'Area'
        db.delete_table('areas')
        
        # Deleting model 'ChairsHistory'
        db.delete_table('chairs_history')
        
        # Deleting model 'Acronym'
        db.delete_table('acronym')
        
        # Deleting model 'WGChair'
        db.delete_table('g_chairs')
        
        # Deleting model 'WGEditor'
        db.delete_table('g_editors')
        
        # Deleting model 'PersonOrOrgInfo'
        db.delete_table('person_or_org_info')
        
        # Deleting model 'Position'
        db.delete_table('ballots')
        
        # Deleting model 'IESGComment'
        db.delete_table('ballots_comment')
        
        # Deleting model 'IESGLogin'
        db.delete_table('iesg_login')
        
        # Deleting model 'AreaWGURL'
        db.delete_table('wg_www_pages')
        
        # Deleting model 'IDSubState'
        db.delete_table('sub_state')
        
        # Deleting model 'DocumentComment'
        db.delete_table('document_comments')
        
    
    
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
            'time': ('django.db.models.fields.CharField', [], {'default': "'05:06:33'", 'max_length': '20', 'db_column': "'comment_time'"}),
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
