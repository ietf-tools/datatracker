from django.conf.urls import patterns

from ietf.submit import views

urlpatterns = patterns('ietf.submit.views',
    (r'^$', views.upload_submission),
    (r'^status/$', views.search_submission),
    (r'^status/(?P<submission_id>\d+)/$', views.submission_status),
    (r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.submission_status),
    (r'^status/(?P<submission_id>\d+)/confirm/(?P<auth_token>[a-f\d]+)/$', views.confirm_submission),
    (r'^status/(?P<submission_id>\d+)/edit/$', views.edit_submission),
    (r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]+)/edit/$', views.edit_submission),
    (r'^note-well/$', views.note_well),
    (r'^tool-instructions/$', views.tool_instructions),

    (r'^approvals/$', views.approvals),
    (r'^approvals/addpreapproval/$', views.add_preapproval),
    (r'^approvals/cancelpreapproval/(?P<preapproval_id>[a-f\d]+)/$', views.cancel_preapproval),

    (r'^manualpost/$', views.manualpost),
    (r'^manualpost/addemail$', views.add_manualpost_email),
    (r'^manualpost/addemail/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.add_manualpost_email),
    (r'^manualpost/attachment/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<filename>.*)$', views.show_submission_email_attachment),
    (r'^manualpost/cancel$', views.cancel_waiting_for_draft),
    (r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', views.show_submission_email_message),
    (r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.show_submission_email_message),
    (r'^manualpost/replyemail/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', views.send_submission_email),
    (r'^manualpost/sendemail/(?P<submission_id>\d+)/$', views.send_submission_email),
)
