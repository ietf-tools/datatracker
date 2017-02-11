
from ietf.submit import views
from ietf.utils.urls import url

urlpatterns = [ 
    url(r'^$', views.upload_submission),
    url(r'^status/$', views.search_submission),
    url(r'^status/(?P<submission_id>\d+)/$', views.submission_status),
    url(r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.submission_status),
    url(r'^status/(?P<submission_id>\d+)/confirm/(?P<auth_token>[a-f\d]+)/$', views.confirm_submission),
    url(r'^status/(?P<submission_id>\d+)/edit/$', views.edit_submission),
    url(r'^status/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]+)/edit/$', views.edit_submission),
    url(r'^note-well/$', views.note_well),
    url(r'^tool-instructions/$', views.tool_instructions),

    url(r'^approvals/$', views.approvals),
    url(r'^approvals/addpreapproval/$', views.add_preapproval),
    url(r'^approvals/cancelpreapproval/(?P<preapproval_id>[a-f\d]+)/$', views.cancel_preapproval),

    url(r'^manualpost/$', views.manualpost),
    url(r'^manualpost/addemail$', views.add_manualpost_email),
    url(r'^manualpost/addemail/(?P<submission_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.add_manualpost_email),
    url(r'^manualpost/attachment/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<filename>.*)$', views.show_submission_email_attachment),
    url(r'^manualpost/cancel$', views.cancel_waiting_for_draft),
    url(r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', views.show_submission_email_message),
    url(r'^manualpost/email/(?P<submission_id>\d+)/(?P<message_id>\d+)/(?P<access_token>[a-f\d]*)/$', views.show_submission_email_message),
    url(r'^manualpost/replyemail/(?P<submission_id>\d+)/(?P<message_id>\d+)/$', views.send_submission_email),
    url(r'^manualpost/sendemail/(?P<submission_id>\d+)/$', views.send_submission_email),
]
