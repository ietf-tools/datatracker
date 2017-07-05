
from ietf.secr.meetings import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^add/$', views.add),
    url(r'^ajax/get-times/(?P<meeting_id>\d{1,6})/(?P<day>\d)/$', views.ajax_get_times),
    url(r'^blue_sheet/$', views.blue_sheet_redirect),
    url(r'^(?P<meeting_id>\d{1,6})/$', views.view),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/$', views.blue_sheet),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/generate/$', views.blue_sheet_generate),
    url(r'^(?P<meeting_id>\d{1,6})/edit/$', views.edit_meeting),
    url(r'^(?P<meeting_id>\d{1,6})/notifications/$', views.notifications),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/$', views.select),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/$', views.non_session),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/edit/(?P<slot_id>\d{1,6})/$', views.non_session_edit),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/delete/(?P<slot_id>\d{1,6})/$', views.non_session_delete),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/rooms/$', views.rooms),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/select/$', views.select_group),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/$', views.times),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/delete/(?P<time>[0-9\:]+)/$', views.times_delete),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/edit/(?P<time>[0-9\:]+)/$', views.times_edit),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/unschedule/(?P<session_id>\d{1,6})/$', views.unschedule),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/(?P<acronym>[-a-z0-9]+)/schedule/$', views.schedule),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/(?P<session_id>\d{1,6})/edit/$', views.session_edit),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<acronym>[-a-z0-9]+)/remove/$', views.remove_session),
]
