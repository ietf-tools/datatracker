# Copyright The IETF Trust 2007-2019, All Rights Reserved

from ietf.secr.meetings import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^add/$', views.add),
    # url(r'^ajax/get-times/(?P<meeting_id>\d{1,6})/(?P<day>\d)/$', views.ajax_get_times), # Not in use
    url(r'^blue_sheet/$', views.blue_sheet_redirect),
    url(r'^(?P<meeting_id>\d{1,6})/$', views.view),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/$', views.blue_sheet),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/generate/$', views.blue_sheet_generate),
    url(r'^(?P<meeting_id>\d{1,6})/edit/$', views.edit_meeting),
    url(r'^(?P<meeting_id>\d{1,6})/notifications/$', views.notifications),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/$', views.rooms),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/miscsessions/$', views.misc_sessions),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/miscsessions/cancel/(?P<slot_id>\d{1,6})/$', views.misc_session_cancel),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/miscsessions/edit/(?P<slot_id>\d{1,6})/$', views.misc_session_edit),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/miscsessions/delete/(?P<slot_id>\d{1,6})/$', views.misc_session_delete),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/rooms/$', views.rooms),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/$', views.times),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/regularsessions/$', views.regular_sessions),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/delete/(?P<time>[0-9\:]+)/$', views.times_delete),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/edit/(?P<time>[0-9\:]+)/$', views.times_edit),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/(?P<session_id>\d{1,6})/edit/$', views.regular_session_edit),
]
