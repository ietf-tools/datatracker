# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def make_recipients(apps):

    Recipient=apps.get_model('mailtrigger','Recipient')

    rc = Recipient.objects.create

    rc(slug='iesg',
       desc='The IESG',
       template='The IESG <iesg@ietf.org>')

    rc(slug='iab',
       desc='The IAB',
       template='The IAB <iab@iab.org>')

    rc(slug='ietf_announce',
       desc='The IETF Announce list',
       template='IETF-Announce <ietf-announce@ietf.org>')

    rc(slug='rfc_editor',
       desc='The RFC Editor',
       template='<rfc-editor@rfc-editor.org>')

    rc(slug='iesg_secretary',
       desc='The Secretariat',
       template='<iesg-secretary@ietf.org>')

    rc(slug='ietf_secretariat',
       desc='The Secretariat',
       template='<ietf-secretariat-reply@ietf.org>')

    rc(slug='doc_authors',
       desc="The document's authors",
       template='{% if doc.type_id == "draft" %}<{{doc.name}}@ietf.org>{% endif %}')

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
       template='{% if doc.shepherd %}<{{doc.shepherd.address}}>{% endif %}' )

    rc(slug='doc_ad',
       desc="The document's responsible Area Director",
       template='{% if doc.ad %}<{{doc.ad.email_address}}>{% endif %}' )

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
       template=None )

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
       template='{% if group.list_email %}<{{ group.list_email }}>{% endif %}')

    rc(slug='group_steering_group',
       desc="The group's steering group (IESG or IRSG)",
       template=None)

    rc(slug='group_chairs',
       desc="The group's chairs",
       template="{% if group and group.acronym %}<{{group.acronym}}-chairs@ietf.org>{% endif %}")

    rc(slug='group_responsible_directors',
       desc="The group's responsible AD(s) or IRTF chair",
       template=None)

    rc(slug='doc_group_responsible_directors',
       desc="The document's group's responsible AD(s) or IRTF chair",
       template=None)

    rc(slug='internet_draft_requests',
       desc="The internet drafts ticketing system",
       template='<internet-drafts@ietf.org>')

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
       template='<session-request@ietf.org>')

    rc(slug='session_requester',
       desc="The person that requested a meeting slot for a given group",
       template=None)

    rc(slug='logged_in_person',
       desc="The person currently logged into the datatracker who initiated a given action",
       template='{% if person and person.email_address %}<{{ person.email_address }}>{% endif %}')

    rc(slug='ipr_requests',
       desc="The ipr disclosure handling system",
       template='<ietf-ipr@ietf.org>')

    rc(slug='ipr_submitter',
       desc="The submitter of an IPR disclosure",
       template='{% if ipr.submitter_email %}{{ ipr.submitter_email }}{% endif %}')

    rc(slug='ipr_updatedipr_contacts',
       desc="The submitter (or ietf participant if the submitter is not available) "
             "of all IPR disclosures updated directly by this disclosure, without recursing "
             "to what the updated disclosures might have updated.",
       template=None)

    rc(slug='ipr_updatedipr_holders',
       desc="The holders of all IPR disclosures updated by disclosure and disclosures updated by those and so on.",
       template=None)

    rc(slug='ipr_announce',
       desc="The IETF IPR announce list",
       template='ipr-announce@ietf.org')

    rc(slug='doc_ipr_group_or_ad',
       desc="Leadership for a document that has a new IPR disclosure",
       template=None)

    rc(slug='liaison_to_contacts',
       desc="The addresses captured in the To field of the liaison statement form",
       template='{{liaison.to_contacts}}')

    rc(slug='liaison_cc',
       desc="The addresses captured in the Cc field of the liaison statement form",
       template='{{liaison.cc_contacts}}')

    rc(slug='liaison_technical_contacts',
       desc="The addresses captured in the technical contact field of the liaison statement form",
       template='{{liaison.technical_contacts}}')

    rc(slug='liaison_response_contacts',
       desc="The addresses captured in the response contact field of the liaison statement form",
       template='{{liaison.response_contacts}}')
 
    rc(slug='liaison_approvers',
       desc="The set of people who can approve this liasion statemetns",
       template='{{liaison.approver_emails|join:", "}}')

    rc(slug='liaison_manager',
       desc="The assigned liaison manager for an external group ",
       template=None)

    rc(slug='nominator',
       desc="The person that submitted a nomination to nomcom",
       template='{{nominator}}')

    rc(slug='nominee',
       desc="The person nominated for a position",
       template='{{nominee}}')

    rc(slug='nomcom_chair',
       desc="The chair of a given nomcom",
       template='{{nomcom.group.get_chair.email.address}}')

    rc(slug='commenter',
       desc="The person providing a comment to nomcom",
       template='{{commenter}}')

    rc(slug='new_work',
       desc="The IETF New Work list",
       template='<new-work@ietf.org>')

def make_mailtriggers(apps):

    Recipient=apps.get_model('mailtrigger','Recipient')
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')

    def mt_factory(slug,desc,to_slugs,cc_slugs=[]):

        # Try to protect ourselves from typos
        all_slugs = to_slugs[:]
        all_slugs.extend(cc_slugs)
        for recipient_slug in all_slugs:
            try:
                Recipient.objects.get(slug=recipient_slug)
            except Recipient.DoesNotExist:
                print "****Some rule tried to use",recipient_slug
                raise

        m = MailTrigger.objects.create(slug=slug, desc=desc)
        m.to = Recipient.objects.filter(slug__in=to_slugs)
        m.cc = Recipient.objects.filter(slug__in=cc_slugs)

    mt_factory(slug='ballot_saved',
               desc="Recipients when a new ballot position "
                    "(with discusses, other blocking positions, "
                    "or comments) is saved",
               to_slugs=['iesg'],
               cc_slugs=['doc_notify',
                         'doc_group_mail_list',
                         'doc_authors',
                         'doc_group_chairs',
                         'doc_shepherd',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                         'conflict_review_stream_manager',
                        ]
              )

    mt_factory(slug='ballot_deferred',
               desc="Recipients when a ballot is deferred to "
                    "or undeferred from a future telechat",
               to_slugs=['iesg',
                         'iesg_secretary',
                         'doc_group_chairs',
                         'doc_notify',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                         'conflict_review_stream_manager',
                        ],
              )

    mt_factory(slug='ballot_approved_ietf_stream',
               desc="Recipients when an IETF stream document ballot is approved",
               to_slugs=['ietf_announce'],
               cc_slugs=['iesg',
                         'doc_notify',
                         'doc_ad',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_group_mail_list',
                         'doc_group_chairs',
                         'rfc_editor',
                         ],
              )
 
    mt_factory(slug='ballot_approved_ietf_stream_iana',
               desc="Recipients for IANA message when an IETF stream document ballot is approved",
               to_slugs=['iana_approve'])

    mt_factory(slug='ballot_approved_conflrev',
               desc="Recipients when a conflict review ballot is approved",
               to_slugs=['conflict_review_stream_manager',
                         'conflict_review_steering_group',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                         'doc_notify',
                        ],
               cc_slugs=['iesg',
                         'ietf_announce',
                         'iana',
                        ],
              )

    mt_factory(slug='ballot_approved_charter',
               desc="Recipients when a charter is approved",
               to_slugs=['ietf_announce',],
               cc_slugs=['group_mail_list',
                         'group_steering_group',
                         'group_chairs',
                         'doc_notify',
                        ],
              )
            
    mt_factory(slug='ballot_approved_status_change',
               desc="Recipients when a status change is approved",
               to_slugs=['ietf_announce',],
               cc_slugs=['iesg',
                         'rfc_editor',
                         'doc_notify',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ],
              )

    mt_factory(slug='ballot_issued',
               desc="Recipients when a ballot is issued",
               to_slugs=['iesg',])

    mt_factory(slug='ballot_issued_iana',
               desc="Recipients for IANA message when a ballot is issued",
               to_slugs=['iana_eval',])

    mt_factory(slug='last_call_requested',
               desc="Recipients when AD requests a last call",
               to_slugs=['iesg_secretary',],
               cc_slugs=['doc_ad',
                         'doc_shepherd',
                         'doc_notify',
                        ],
              )

    mt_factory(slug='last_call_issued',
               desc="Recipients when a last call is issued",
               to_slugs=['ietf_announce',],
               cc_slugs=['doc_ad',
                         'doc_shepherd',
                         'doc_authors',
                         'doc_notify',
                         'doc_group_mail_list',
                         'doc_group_chairs',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ]
              )

    mt_factory(slug='last_call_issued_iana',
               desc="Recipients for IANA message when a last call is issued",
               to_slugs=['iana_last_call'])

    mt_factory(slug='last_call_expired',
               desc="Recipients when a last call has expired",
               to_slugs=['doc_ad',
                         'doc_notify',
                         'doc_authors',
                         'doc_shepherd',
                        ],
               cc_slugs=['iesg_secretary',],
              )

    mt_factory(slug='pubreq_iesg',
               desc="Recipients when a draft is submitted to the IESG",
               to_slugs=['doc_ad',],
               cc_slugs=['iesg_secretary',
                         'doc_notify',
                         'doc_shepherd',
                         'doc_group_chairs',
                        ],
              )

    mt_factory(slug='pubreq_rfced',
               desc="Recipients when a non-IETF stream manager requests publication",
               to_slugs=['rfc_editor',])

    mt_factory(slug='pubreq_rfced_iana',
               desc="Recipients for IANA message when a non-IETF stream manager "
                    "requests publication",
               to_slugs=['iana_approve',])

    mt_factory(slug='charter_internal_review',
               desc="Recipients for message noting that internal review has "
                     "started on a charter",
               to_slugs=['iesg',
                         'iab',
                        ])
               
    mt_factory(slug='charter_external_review',
               desc="Recipients for a charter external review",
               to_slugs=['ietf_announce',],
               cc_slugs=['group_mail_list',], 
              ) 

    mt_factory(slug='charter_external_review_new_work',
               desc="Recipients for a message to new-work about a charter review",
               to_slugs=['new_work',])

    mt_factory(slug='conflrev_requested',
               desc="Recipients for a stream manager's request for an IETF conflict review",
               to_slugs=['iesg_secretary'],
               cc_slugs=['iesg',
                         'doc_notify',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ],
              )

    mt_factory(slug='conflrev_requested_iana',
               desc="Recipients for IANA message when a stream manager requests "
                    "an IETF conflict review",
               to_slugs=['iana_eval',])

    mt_factory(slug='doc_stream_changed',
               desc="Recipients for notification when a document's stream changes",
               to_slugs=['doc_authors',
                         'stream_managers',
                         'doc_notify',
                        ])

    mt_factory(slug='doc_stream_state_edited',
               desc="Recipients when the stream state of a document is manually edited",
               to_slugs=['doc_group_chairs',
                         'doc_group_delegates',
                         'doc_shepherd',
                         'doc_authors',
                        ]) 

    mt_factory(slug='group_milestones_edited',
               desc="Recipients when any of a group's milestones are edited",
               to_slugs=['group_responsible_directors',
                         'group_chairs',
                        ])
               
    mt_factory(slug='group_approved_milestones_edited',
               desc="Recipients when the set of approved milestones for a group are edited",
               to_slugs=['group_mail_list',
                        ])

    mt_factory(slug='doc_state_edited',
               desc="Recipients when a document's state is manually edited",
               to_slugs=['doc_notify',
                         'doc_ad',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_affecteddoc_authors',
                         'doc_group_responsible_directors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ])

    mt_factory(slug='doc_iana_state_changed',
               desc="Recipients when IANA state information for a document changes ",
               to_slugs=['doc_notify',
                         'doc_ad',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ])

    mt_factory(slug='doc_telechat_details_changed',
               desc="Recipients when a document's telechat date or other "
                    "telechat specific details are changed",
               to_slugs=['iesg',
                         'iesg_secretary',
                         'doc_notify',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_affecteddoc_authors',
                         'doc_affecteddoc_group_chairs',
                         'doc_affecteddoc_notify',
                        ])

    mt_factory(slug='doc_pulled_from_rfc_queue',
               desc="Recipients when a document is taken out of the RFC's editor queue "
                    "before publication",
               to_slugs=['iana',
                         'rfc_editor',
                        ],
               cc_slugs=['iesg_secretary',
                         'iesg', 
                         'doc_notify',
                         'doc_authors',
                         'doc_shepherd',
                         'doc_group_chairs',
                        ],
              )

    mt_factory(slug='doc_replacement_changed',
               desc="Recipients when what a document replaces or is replaced by changes",
               to_slugs=['doc_authors',
                         'doc_notify',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_group_responsible_directors',
                        ]) 

    mt_factory(slug='charter_state_edit_admin_needed',
               desc="Recipients for message to adminstrators when a charter state edit "
                    "needs followon administrative action",
               to_slugs=['iesg_secretary'])

    mt_factory(slug='group_closure_requested',
               desc="Recipients for message requesting closure of a group",
               to_slugs=['iesg_secretary'])

    mt_factory(slug='doc_expires_soon',
               desc="Recipients for notification of impending expiration of a document",
               to_slugs=['doc_authors'],
               cc_slugs=['doc_notify',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_group_responsible_directors',
                        ],
              )

    mt_factory(slug='doc_expired',
               desc="Recipients for notification of a document's expiration",
               to_slugs=['doc_authors'],
               cc_slugs=['doc_notify',
                         'doc_shepherd',
                         'doc_group_chairs',
                         'doc_group_responsible_directors',
                        ],
              )

    mt_factory(slug='resurrection_requested',
               desc="Recipients of a request to change the state of a draft away from 'Dead'",
               to_slugs=['internet_draft_requests',])

    mt_factory(slug='resurrection_completed',
               desc="Recipients when a draft resurrection request has been completed",
               to_slugs=['iesg_secretary',
                         'doc_ad',
                        ])

    mt_factory(slug='sub_manual_post_requested',
               desc="Recipients for a manual post request for a draft submission",
               to_slugs=['internet_draft_requests',],
               cc_slugs=['submission_submitter',
                         'submission_authors',
                         'submission_group_chairs',
                        ],
              )

    mt_factory(slug='sub_chair_approval_requested',
               desc="Recipients for a message requesting group chair approval of "
                    "a draft submission",
               to_slugs=['submission_group_chairs',])

    mt_factory(slug='sub_confirmation_requested',
               desc="Recipients for a message requesting confirmation of a draft submission",
               to_slugs=['submission_confirmers',])

    mt_factory(slug='sub_management_url_requested',
               desc="Recipients for a message with the full URL for managing a draft submission",
               to_slugs=['submission_confirmers',])

    mt_factory(slug='sub_announced',
               desc="Recipients for the announcement of a successfully submitted draft",
               to_slugs=['ietf_announce',
                        ],
               cc_slugs=['submission_group_mail_list',
                        ],
              )

    mt_factory(slug='sub_announced_to_authors',
               desc="Recipients for the announcement to the authors of a successfully "
                    "submitted draft",
               to_slugs=['submission_authors',
                         'submission_confirmers',
                        ])

    mt_factory(slug='sub_new_version',
               desc="Recipients for notification of a new version of an existing document",
               to_slugs=['doc_notify',
                         'doc_ad',
                         'doc_non_ietf_stream_manager',
                         'rfc_editor_if_doc_in_queue',
                         'doc_discussing_ads',
                        ])

    mt_factory(slug='group_personnel_change',
               desc="Recipients for a message noting changes in a group's personnel",
               to_slugs=['iesg_secretary',
                         'group_responsible_directors',
                         'group_chairs',
                         'group_changed_personnel',
                        ])

    mt_factory(slug='session_requested',
               desc="Recipients for a normal meeting session request",
               to_slugs=['session_requests', ], 
               cc_slugs=['group_mail_list',
                         'group_chairs',
                         'group_responsible_directors',
                         'logged_in_person',
                        ],
              ) 

    mt_factory(slug='session_requested_long',
               desc="Recipients for a meeting session request for more than 2 sessions",
               to_slugs=['group_responsible_directors', ],
               cc_slugs=['session_requests',
                         'group_chairs',
                         'logged_in_person',
                               ],
              )

    mt_factory(slug='session_request_cancelled',
               desc="Recipients for a message cancelling a session request",
               to_slugs=['session_requests', ],
               cc_slugs=['group_mail_list',
                         'group_chairs',
                         'group_responsible_directors',
                         'logged_in_person',
                        ],
              )

    mt_factory(slug='session_request_not_meeting',
               desc="Recipients for a message noting a group plans to not meet",
               to_slugs=['session_requests', ],
               cc_slugs=['group_mail_list',
                         'group_chairs',
                         'group_responsible_directors',
                         'logged_in_person',
                        ], 
              )

    mt_factory(slug='session_scheduled',
               desc="Recipients for details when a session has been scheduled",
               to_slugs=['session_requester',
                         'group_chairs',
                        ],
               cc_slugs=['group_mail_list',
                         'group_responsible_directors',
                        ],
              )

    mt_factory(slug='ipr_disclosure_submitted',
               desc="Recipients when an IPR disclosure is submitted",
               to_slugs=['ipr_requests', ])

    mt_factory(slug='ipr_disclosure_followup',
               desc="Recipients when the secretary follows up on an IPR disclosure submission",
               to_slugs=['ipr_submitter', ],)

    mt_factory(slug='ipr_posting_confirmation',
               desc="Recipients for a message confirming that a disclosure has been posted",
               to_slugs=['ipr_submitter', ],
               cc_slugs=['ipr_updatedipr_contacts',
                         'ipr_updatedipr_holders',
                        ],
              )

    mt_factory(slug='ipr_posted_on_doc',
               desc="Recipients when an IPR disclosure calls out a given document",
               to_slugs=['doc_authors', ], 
               cc_slugs=['doc_ipr_group_or_ad',
                         'ipr_announce',
                        ], 
              )

    mt_factory(slug='liaison_statement_posted',
               desc="Recipient for a message when a new liaison statement is posted",
               to_slugs=['liaison_to_contacts', ],
               cc_slugs=['liaison_cc',
                         'liaison_technical_contacts',
                         'liaison_response_contacts',
                        ],
              )

    mt_factory(slug='liaison_approval_requested',
               desc="Recipients for a message that a pending liaison statement needs approval",
               to_slugs=['liaison_approvers',
                        ])

    mt_factory(slug='liaison_deadline_soon',
               desc="Recipients for a message about a liaison statement deadline that is "
                    "approaching.",
               to_slugs=['liaison_to_contacts',
                        ],
               cc_slugs=['liaison_cc',
                         'liaison_technical_contacts',
                         'liaison_response_contacts',
                        ],
              )

    mt_factory(slug='liaison_manager_update_request',
               desc="Recipients for a message requesting an updated list of authorized individuals",
               to_slugs=['liaison_manager', ])

    mt_factory(slug='nomination_received',
               desc="Recipients for a message noting a new nomination has been received",
               to_slugs=['nomcom_chair', ])

    mt_factory(slug='nomination_receipt_requested',
               desc="Recipients for a message confirming a nomination was made",
               to_slugs=['nominator', ])

    mt_factory(slug='nomcom_comment_receipt_requested',
               desc="Recipients for a message confirming a comment was made",
               to_slugs=['commenter', ])

    mt_factory(slug='nomination_created_person',
               desc="Recipients for a message noting that a nomination caused a "
                     "new Person record to be created in the datatracker",
               to_slugs=['ietf_secretariat',
                         'nomcom_chair',
                        ],
              )

    mt_factory(slug='nomination_new_nominee',
               desc="Recipients the first time a person is nominated for a position, "
                     "asking them to accept or decline the nomination",
               to_slugs=['nominee', ])

    mt_factory(slug='nomination_accept_reminder',
               desc="Recipeints of message reminding a nominee to accept or decline a nomination",
               to_slugs=['nominee', ])

    mt_factory(slug='nomcom_questionnaire',
               desc="Recipients for the questionairre that nominees should complete",
               to_slugs=['nominee', ])

    mt_factory(slug='nomcom_questionnaire_reminder',
               desc="Recipients for a message reminding a nominee to return a "
                    "completed questionairre response",
               to_slugs=['nominee', ])

    mt_factory(slug='doc_replacement_suggested',
               desc="Recipients for suggestions that this doc replaces or is replace by "
                     "some other document",
               to_slugs=['doc_group_chairs',
                         'doc_group_responsible_directors',
                         'doc_non_ietf_stream_manager',
                         'iesg_secretary',
                        ])

    mt_factory(slug='doc_adopted_by_group',
               desc="Recipients for notification that a document has been adopted by a group",
               to_slugs=['doc_authors',
                         'doc_group_chairs',
                         'doc_group_mail_list',
                        ],
               cc_slugs=['doc_ad',
                         'doc_shepherd',
                         'doc_notify',
                        ],
              )

    mt_factory(slug='doc_added_comment',
               desc="Recipients for a message when a new comment is manually entered into the document's history",
               to_slugs=['doc_authors',
                         'doc_group_chairs',
                         'doc_shepherd',
                         'doc_group_responsible_directors', 
                         'doc_non_ietf_stream_manager',
                        ])

    mt_factory(slug='doc_intended_status_changed',
               desc="Recipients for a message when a document's intended "
                    "publication status changes",
               to_slugs=['doc_authors',
                         'doc_group_chairs',
                         'doc_shepherd',
                         'doc_group_responsible_directors', 
                         'doc_non_ietf_stream_manager',
                        ])

    mt_factory(slug='doc_iesg_processing_started',
               desc="Recipients for a message when the IESG begins processing a document ",
               to_slugs=['doc_authors',
                         'doc_ad',
                         'doc_shepherd',
                         'doc_group_chairs',
                        ])

def forward(apps, schema_editor):

    make_recipients(apps)
    make_mailtriggers(apps)

def reverse(apps, schema_editor):

    Recipient=apps.get_model('mailtrigger','Recipient')
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')

    Recipient.objects.all().delete()
    MailTrigger.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
