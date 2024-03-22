
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
    url(r'^tool-instructions/$', views.tool_instructions),

    url(r'^approvals/$', views.approvals),
    url(r'^approvals/addpreapproval/$', views.add_preapproval),
    url(r'^approvals/cancelpreapproval/(?P<preapproval_id>[a-f\d]+)/$', views.cancel_preapproval),

    url(r'^manualpost/$', views.manualpost),
    # proof-of-concept for celery async tasks
    url(r'^async-poke/?$', views.async_poke_test),
]
