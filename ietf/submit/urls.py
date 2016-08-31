from django.conf.urls import patterns, url


urlpatterns = patterns('ietf.submit.views',
    url(r'^$', 'upload_submission', name='submit_upload_submission'),
    url(r'^status/$', 'search_submission', name='submit_search_submission'),
    url(r'^status/(?P<submission_id>\d+)/$', 'submission_status', name='submit_submission_status'),
    url(r'^status/(?P<submission_id>\d+)/edit/$', 'edit_submission', name='submit_edit_submission'),
    url(r'^status/(?P<submission_id>\d+)/confirm/(?P<auth_token>[a-f\d]+)/$', 'confirm_submission', name='submit_confirm_submission'),
    url(r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', 'submission_status', name='submit_submission_status_by_hash'),
    url(r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]+)/edit/$', 'edit_submission', name='submit_edit_submission_by_hash'),
    url(r'^note-well/$', 'note_well', name='submit_note_well'),
    url(r'^tool-instructions/$', 'tool_instructions', name='submit_tool_instructions'),

    url(r'^approvals/$', 'approvals', name='submit_approvals'),
    url(r'^approvals/addpreapproval/$', 'add_preapproval', name='submit_add_preapproval'),
    url(r'^approvals/cancelpreapproval/(?P<preapproval_id>[a-f\d]+)/$', 'cancel_preapproval', name='submit_cancel_preapproval'),

    url(r'^manualpost/addemail$', 'add_manualpost_email', name='submit_manualpost_email'),
    url(r'^manualpost/addemail/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', 'add_manualpost_email', name='submit_manualpost_email_by_hash'),
    url(r'^awaitingdraft/cancel$', 'cancel_awaiting_draft', name='submit_cancel_awaiting_draft_by_hash'),
    url(r'^manualpost/$', 'manualpost', name='submit_manualpost'),
    url(r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', 'submission_email', name='submit_submission_email'),
    url(r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<access_token>[a-f\d]*)/$', 'submission_email', name='submit_submission_email_by_hash'),
    url(r'^manualpost/sendemail/(?P<submission_id>\d+)/$', 'send_email', name='submission_send_email'),
    url(r'^manualpost/replyemail/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', 'send_email', name='submission_reply_email'),
    url(r'^manualpost/attachment/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<filename>.*)$', 'submission_email_attachment', name='submit_submission_email_attachment'),
)
