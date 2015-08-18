# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def make_recipients(apps):

    Recipient=apps.get_model('mailtoken','Recipient')

    rc = Recipient.objects.create

    rc(slug='iesg',
       desc='The IESG',
       template='The IESG <iesg@ietf.org>')

    rc(slug='ietf_announce',
       desc='The IETF Announce list',
       template='IETF-Announce <ietf-announce@ietf.org>')

    rc(slug='rfc_editor',
       desc='The RFC Editor',
       template='<rfc-editor@rfc-editor.org>')

    rc(slug='iesg_secretary',
       desc='The Secretariat',
       template='<iesg-secretary@ietf.org>')

    rc(slug='doc_authors',
       desc="The document's authors",
       template='{% if doc.type_id == "draft" %}{{doc.name}}@ietf.org{% endif %}')

    rc(slug='doc_notify',
       desc="The addresses in the document's notify field",
       template='{{doc.notify}}')

    rc(slug='doc_group_chairs',
       desc="The document's group chairs (if the document is assigned to a working or research group)",
       template=None)

    rc(slug='doc_group_delegates',
       desc="The document's group delegates (if the document is assigned to a working or research group)",
       template=None)

    rc(slug='doc_affecteddoc_authors',
       desc="The authors of the subject documents of a conflict-review or status-change",
       template=None)

    rc(slug='doc_affecteddoc_group_chairs',
       desc="The chairs of groups of the subject documents of a conflict-review or status-change",
       template=None)

    rc(slug='doc_affecteddoc_notify',
       desc="The notify field of the subject documents of a conflict-review or status-change",
       template=None)

    rc(slug='doc_shepherd',
       desc="The document's shepherd",
       template='{% if doc.shepherd %}{{doc.shepherd.address}}{% endif %}' )

    rc(slug='doc_ad',
       desc="The document's responsible Area Director",
       template='{% if doc.ad %}{{doc.ad.email_address}}{% endif %}' )

    rc(slug='doc_group_mail_list',
       desc="The list address of the document's group",
       template=None )

    rc(slug='doc_stream_manager',
       desc="The manager of the document's stream",
       template=None )

    rc(slug='stream_managers',
       desc="The managers of any related streams",
       template=None )

    rc(slug='conflict_review_stream_manager',
       desc="The stream manager of a document being reviewed for IETF stream conflicts",
       template = None )

    rc(slug='conflict_review_steering_group',
       desc="The steering group (e.g. IRSG) of a document being reviewed for IETF stream conflicts",
       template = None)

    rc(slug='iana_approve',
       desc="IANA's draft approval address",
       template='IANA <drafts-approval@icann.org>')

    rc(slug='iana_last_call',
       desc="IANA's draft last call address",
       template='IANA <drafts-lastcall@icann.org>')

    rc(slug='iana_eval',
       desc="IANA's draft evaluation address",
       template='IANA <drafts-eval@icann.org>')

    rc(slug='iana',
       desc="IANA",
       template='<iana@iana.org>')

    rc(slug='group_mail_list',
       desc="The group's mailing list",
       template='{{ group.list_email }}')

    rc(slug='group_steering_group',
       desc="The group's steering group (IESG or IRSG)",
       template=None)

    rc(slug='group_chairs',
       desc="The group's chairs",
       template="{{group.acronym}}-chairs@ietf.org")

    rc(slug='group_responsible_directors',
       desc="The group's responsible AD(s) or IRTF chair",
       template=None)

    rc(slug='doc_group_responsible_directors',
       desc="The document's group's responsible AD(s) or IRTF chair",
       template=None)

    rc(slug='internet_draft_requests',
       desc="The internet drafts ticketing system",
       template='internet-drafts@ietf.org')

    rc(slug='submission_submitter',
       desc="The person that submitted a draft",
       template='{{submission.submitter}}')

    rc(slug='submission_authors',
       desc="The authors of a submitted draft",
       template=None)

    rc(slug='submission_group_chairs',
       desc="The chairs of a submitted draft belonging to a group",
       template=None)

    rc(slug='submission_confirmers',
       desc="The people who can confirm a draft submission",
       template=None)

    rc(slug='submission_group_mail_list',
       desc="The people who can confirm a draft submission",
       template=None)

    rc(slug='doc_non_ietf_stream_manager',
       desc="The document's stream manager if the document is not in the IETF stream",
       template=None)

    rc(slug='rfc_editor_if_doc_in_queue',
       desc="The RFC Editor if a document is in the RFC Editor queue",
       template=None)

    rc(slug='doc_discussing_ads',
       desc="Any ADs holding an active DISCUSS position on a given document",
       template=None)

    rc(slug='group_changed_personnel',
       desc="Any personnel who were added or deleted when a group's personnel changes",
       template='{{ changed_personnel | join:", " }}')

    rc(slug='session_requests',
       desc="The session request ticketing system",
       template='session-request@ietf.org')

    rc(slug='ipr_requests',
       desc="The ipr disclosure handling system",
       template='ietf-ipr@ietf.org')

    rc(slug='logged_in_person',
       desc="The person currently logged into the datatracker who initiated a given action",
       template='{% if person and person.email_address %}{{ person.email_address }}{% endif %}')

def make_mailtokens(apps):

    Recipient=apps.get_model('mailtoken','Recipient')
    MailToken=apps.get_model('mailtoken','MailToken')

    def mt_factory(slug,desc,recipient_slugs):
        m = MailToken.objects.create(slug=slug, desc=desc)
        m.recipients = Recipient.objects.filter(slug__in=recipient_slugs)

    mt_factory(slug='ballot_saved',
               desc='Recipients when a new ballot position (with discusses, other blocking positions, or comments) is saved',
               recipient_slugs=['iesg'])

    mt_factory(slug='ballot_saved_cc',
               desc='Copied when a new ballot position (with discusses, other blocking positions, or comments) is saved',
               recipient_slugs=['doc_authors',
                                'doc_group_chairs',
                                'doc_shepherd',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                                'conflict_review_stream_manager',
                                ])

    mt_factory(slug='ballot_deferred',
               desc='Recipients when a ballot is deferred to or undeferred from a future telechat',
               recipient_slugs=['iesg',
                                'iesg_secretary',
                                'doc_group_chairs',
                                'doc_notify',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                                'conflict_review_stream_manager',
                                ])

    mt_factory(slug='ballot_approved_ietf_stream',
               desc='Recipients when an IETF stream document ballot is approved',
               recipient_slugs=['ietf_announce'])

    mt_factory(slug='ballot_approved_ietf_stream_cc',
               desc='Copied when an IETF stream document ballot is approved',
               recipient_slugs=['iesg',
                                'doc_notify',
                                'doc_ad',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_group_mail_list',
                                'doc_group_chairs',
                                'rfc_editor',
                                ])
 
    mt_factory(slug='ballot_approved_ietf_stream_iana',
               desc='Recipients for IANA message when an IETF stream document ballot is approved',
               recipient_slugs=['iana_approve'])

    mt_factory(slug='ballot_approved_conflrev',
               desc='Recipients when a conflict review ballot is approved',
               recipient_slugs=['conflict_review_stream_manager',
                                'conflict_review_steering_group',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                                'doc_notify',
                                ])

    mt_factory(slug='ballot_approved_conflrev_cc',
               desc='Copied when a conflict review ballot is approved',
               recipient_slugs=['iesg',
                                'ietf_announce',
                                'iana',
                                ])

    mt_factory(slug='ballot_approved_charter',
               desc='Recipients when a charter is approved',
               recipient_slugs=['ietf_announce',])
            
    mt_factory(slug='ballot_approved_charter_cc',
               desc='Copied when a charter is approved',
               recipient_slugs=['group_mail_list',
                                'group_steering_group',
                                'group_chairs',
                                'doc_notify',
                               ])
            
    mt_factory(slug='ballot_approved_status_change',
               desc='Recipients when a status change is approved',
               recipient_slugs=['ietf_announce',])
            
    mt_factory(slug='ballot_approved_status_change_cc',
               desc='Copied when a status change is approved',
               recipient_slugs=['iesg',
                                'rfc_editor',
                                'doc_notify',
                                'doc_affectddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                               ])

    mt_factory(slug='last_call_requested',
               desc='Recipients when AD requests a last call',
               recipient_slugs=['iesg_secretary',])

    mt_factory(slug='last_call_requested_cc',
               desc='Copied when AD requests a last call',
               recipient_slugs=['doc_ad',
                                'doc_shepherd',
                                'doc_notify'])

    mt_factory(slug='last_call_issued',
               desc='Recipients when a last call is issued',
               recipient_slugs=['ietf_announce',])

    mt_factory(slug='last_call_issued_cc',
               desc='Copied when a last call is issued',
               recipient_slugs=['doc_ad',
                                'doc_shepherd',
                                'doc_authors',
                                'doc_notify',
                                'doc_group_list_email',
                                'doc_group_chairs',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify'])

    mt_factory(slug='last_call_issued_iana',
               desc='Recipients for IANA message when a last call is issued',
               recipient_slugs=['iana_last_call'])

    mt_factory(slug='last_call_expired',
               desc='Recipients when a last call has expired',
               recipient_slugs=['iesg',
                                'doc_notify',
                                'doc_authors',
                                'doc_shepherd',
                               ])

    mt_factory(slug='last_call_expired_cc',
               desc='Copied when a last call has expired',
               recipient_slugs=['iesg_secretary',])

    mt_factory(slug='pubreq_iesg',
               desc='Recipients when a draft is submitted to the IESG',
               recipient_slugs=['doc_ad',])

    mt_factory(slug='pubreq_iesg_cc',
               desc='Copied when a draft is submitted to the IESG',
               recipient_slugs=['iesg_secretary',
                                'doc_notify',
                                'doc_shepherd',
                                'doc_group_chairs',
                               ])

    mt_factory(slug='pubreq_rfced',
               desc='Recipients when a non-IETF stream manager requests publication',
               recipient_slugs=['rfc_editor',
                               ])

    mt_factory(slug='pubreq_rfced_iana',
               desc='Recipients for IANA message when a non-IETF stream manager requests publication',
               recipient_slugs=['iana_approve',])

    mt_factory(slug='charter_external_review',
               desc='Recipients for a charter external review',
               recipient_slugs=['ietf_announce',]) 

    mt_factory(slug='charter_external_review_cc',
               desc='Copied on a charter external review',
               recipient_slugs=['group_mail_list',]) 

    mt_factory(slug='conflrev_requested',
               desc="Recipients for a stream manager's request for an IETF conflict review",
               recipient_slugs=['iesg_secretary'])

    mt_factory(slug='conflrev_requested_cc',
               desc="Copied on a stream manager's request for an IETF conflict review",
               recipient_slugs=['iesg',
                                'doc_notify',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                               ])

    mt_factory(slug='conflrev_requested_iana',
               desc="Recipients for IANA message when a stream manager requests an IETF conflict review",
               recipient_slugs=['iana_eval',])

    mt_factory(slug='doc_stream_changed',
               desc="Recipients for notification when a document's stream changes",
               recipient_slugs=['stream_managers',
                                'doc_notify',
                               ])

    mt_factory(slug='doc_stream_state_edited',
               desc="Recipients when the stream state of a document is manually edited",
               recipient_slugs=['doc_group_chairs',
                                'doc_group_delegates',
                                'doc_shepherd',
                                'doc_authors',
                               ]) 

    mt_factory(slug='group_milestones_edited',
               desc="Recipients when any of a group's milestones are edited",
               recipient_slugs=['group_responsible_directors',
                                'group_chairs',
                               ])
               
    mt_factory(slug='group_approved_milestones_edited',
               desc="Recipients when the set of approved milestones for a group are edited",
               recipient_slugs=['group_mail_list',
                               ])

    mt_factory(slug='doc_state_edited',
               desc="Recipients when a document's state is manually edited",
               recipient_slugs=['doc_notify',
                                'doc_ad',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                               ])

    mt_factory(slug='doc_iana_state_changed',
               desc="Recipients when IANA state information for a document changes ",
               recipient_slugs=['doc_notify',
                                'doc_ad',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                               ])

    mt_factory(slug='doc_telechat_details_changed',
               desc="Recipients when a document's telechat date or other telechat specific details are changed",
               recipient_slugs=['iesg',
                                'iesg-secretary',
                                'doc_notify',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_affecteddoc_authors',
                                'doc_affecteddoc_group_chairs',
                                'doc_affecteddoc_notify',
                               ])

    mt_factory(slug='doc_pulled_from_rfc_queue',
               desc="Recipients when a document is taken out of the RFC's editor queue before publication",
               recipient_slugs=['iana',
                                'rfc_editor',
                               ])

    mt_factory(slug='doc_pulled_from_rfc_queue_cc',
               desc="Recipients when a document is taken out of the RFC's editor queue before publication",
               recipient_slugs=['iesg-secretary',
                                'doc_ad', 
                                'doc_notify',
                                'doc_authors',
                                'doc_shepherd',
                                'doc_group_chairs',
                               ])

    mt_factory(slug='doc_replacement_changed',
               desc="Recipients when what a document replaces or is replaced by changes",
               recipient_slugs=['doc_authors',
                                'doc_notify',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_group_responsible_directors',
                               ]) 

    mt_factory(slug='charter_state_edit_admin_needed',
               desc="Recipients for message to adminstrators when a charter state edit needs followon administrative action",
               recipient_slugs=['iesg_secretary'])

    mt_factory(slug='group_closure_requested',
               desc="Recipients for message requesting closure of a group",
               recipient_slugs=['iesg_secretary'])

    mt_factory(slug='doc_expires_soon',
               desc="Recipients for notification of impending expiration of a document",
               recipient_slugs=['doc_authors'])

    mt_factory(slug='doc_expires_soon_cc',
               desc="Copied on  notification of impending expiration of a document",
               recipient_slugs=['doc_notify',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_group_responsible_directors',
                               ])

    mt_factory(slug='doc_expired',
               desc="Recipients for notification of a document's expiration",
               recipient_slugs=['doc_authors'])

    mt_factory(slug='doc_expired_cc',
               desc="Copied on notification of a document's expiration",
               recipient_slugs=['doc_notify',
                                'doc_shepherd',
                                'doc_group_chairs',
                                'doc_group_responsible_directors',
                               ])

    mt_factory(slug='resurrection_requested',
               desc="Recipients of a request to change the state of a draft away from 'Dead'",
               recipient_slugs=['internet_draft_requests',])

    mt_factory(slug='resurrection_completed',
               desc="Recipients when a draft resurrection request has been completed",
               recipient_slugs=['iesg_secretary',
                                'doc_ad',
                               ])

    mt_factory(slug='sub_manual_post_requested',
               desc="Recipients for a manual post request for a draft submission",
               recipient_slugs=['internet_draft_requests',
                               ])

    mt_factory(slug='sub_manual_post_requested_cc',
               desc="Copied on a manual post request for a draft submission",
               recipient_slugs=['submission_submitter',
                                'submission_authors',
                                'submission_group_chairs',
                               ])

    mt_factory(slug='sub_chair_approval_requested',
               desc="Recipients for a message requesting group chair approval of a draft submission",
               recipient_slugs=['submission_group_chairs',])

    mt_factory(slug='sub_confirmation_requested',
               desc="Recipients for a message requesting confirmation of a draft submission",
               recipient_slugs=['submission_confirmers',])

    mt_factory(slug='sub_management_url_requested',
               desc="Recipients for a message with the full URL for managing a draft submission",
               recipient_slugs=['submission_confirmers',])

    mt_factory(slug='sub_announced',
               desc="Recipients for the announcement of a successfully submitted draft",
               recipient_slugs=['ietf_announce',
                               ])

    mt_factory(slug='sub_announced_cc',
               desc="Copied on the announcement of a successfully submitted draft",
               recipient_slugs=['submission_group_mail_list',
                               ])

    mt_factory(slug='sub_announced_to_authors',
               desc="Recipients for the announcement to the authors of a successfully submitted draft",
               recipient_slugs=['submission_authors',
                                'submission_confirmers',
                               ])

    mt_factory(slug='sub_new_version',
               desc="Recipients for notification of a new version of an existing document",
               recipient_slugs=['doc_notify',
                                'doc_ad',
                                'non_ietf_stream_manager',
                                'rfc_editor_if_doc_in_queue',
                                'doc_discussing_ads',
                               ])

    mt_factory(slug='milestone_review_reminder',
               desc="Recipients for reminder message that unapproved milestone changes need review",
               recipient_slugs=['group_responsible_directors',
                               ])

    mt_factory(slug='milestone_review_reminder_cc',
               desc="Copied on reminder message that unapproved milestone changes need review",
               recipient_slugs=['group_chairs',
                               ])

    mt_factory(slug='milestones_due_soon',
               desc='Recipients for reminder message for milestones about to become overdue',
               recipient_slugs=['group_chairs',
                               ])

    mt_factory(slug='milestones_overdue',
               desc='Recipients for message about milestones that are overdue',
               recipient_slugs=['group_chairs',
                               ])

    mt_factory(slug='group_personnel_change',
               desc="Recipients for a message noting changes in a group's personnel",
               recipient_slugs=['iesg_secretary',
                                'group_responsible_directors',
                                'group_chairs',
                                'group_changed_personnel',
                               ])

    mt_factory(slug='session_requested',
               desc="Recipients for a normal meeting session request",
               recipient_slugs=['session_requests',
                               ]) 

    mt_factory(slug='session_requested_cc',
               desc="Copied on a normal meeting session request",
               recipient_slugs=['group_mail_list',
                                'group_chairs',
                                'group_responsible_directors',
                                'logged_in_person',
                               ]) 

    mt_factory(slug='session_requested_long',
               desc="Recipients for a meeting session request for more than 2 sessions",
               recipient_slugs=['group_responsible_directors',
                               ])
     
    mt_factory(slug='session_requested_long_cc',
               desc="Copied on a meeting session request for more than 2 sessions",
               recipient_slugs=['session_requests',
                                'group_chairs',
                                'logged_in_person',
                               ])

    mt_factory(slug='session_request_cancelled',
               desc="Recipients for a message cancelling a session request",
               recipient_slugs=['session_requests',
                               ])

    mt_factory(slug='session_request_cancelled_cc',
               desc="Copied on a message cancelling a session request",
               recipient_slugs=['group_mail_list',
                                'group_chairs',
                                'group_responsible_directors',
                                'logged_in_person',
                               ]) 

    mt_factory(slug='session_request_not_meeting',
               desc="Recipients for a message noting a group plans to not meet",
               recipient_slugs=['session_requests',
                               ])

    mt_factory(slug='session_request_not_meeting_cc',
               desc="Copied on a message noting a group plans to not meet",
               recipient_slugs=['group_mail_list',
                                'group_chairs',
                                'group_responsible_directors',
                                'logged_in_person',
                               ]) 

    mt_factory(slug='session_scheduled',
               desc="Recipients for details when a session has been scheduled",
               recipient_slugs=['session_requester',
                                'group_chairs',
                               ])

    mt_factory(slug='session_scheduled_cc',
               desc="Recipients for details when a session has been scheduled",
               recipient_slugs=['group_mail_list',
                                'group_responsible_directors',
                               ])

    mt_factory(slug='ipr_disclosure_submitted',
               desc="Recipients when an IPR notification is submitted",
               recipient_slugs=['ipr_requests',
                               ])

def forward(apps, schema_editor):

    make_recipients(apps)
    make_mailtokens(apps)

def reverse(apps, schema_editor):

    Recipient=apps.get_model('mailtoken','Recipient')
    MailToken=apps.get_model('mailtoken','MailToken')

    Recipient.objects.all().delete()
    MailToken.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtoken', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
