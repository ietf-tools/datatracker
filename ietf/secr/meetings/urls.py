from django.conf.urls import url

from ietf.secr.meetings import views

urlpatterns = [
    url(r'^$', views.main, name='meetings'),
    url(r'^add/$', views.add, name='meetings_add'),
    url(r'^ajax/get-times/(?P<meeting_id>\d{1,6})/(?P<day>\d)/$', views.ajax_get_times, name='meetings_ajax_get_times'),
    url(r'^blue_sheet/$', views.blue_sheet_redirect, name='meetings_blue_sheet_redirect'),
    url(r'^(?P<meeting_id>\d{1,6})/$', views.view, name='meetings_view'),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/$', views.blue_sheet, name='meetings_blue_sheet'),
    url(r'^(?P<meeting_id>\d{1,6})/blue_sheet/generate/$', views.blue_sheet_generate, name='meetings_blue_sheet_generate'),
    url(r'^(?P<meeting_id>\d{1,6})/edit/$', views.edit_meeting, name='meetings_edit_meeting'),
    url(r'^(?P<meeting_id>\d{1,6})/notifications/$', views.notifications, name='meetings_notifications'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/$', views.select, name='meetings_select'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/$', views.non_session, name='meetings_non_session'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/edit/(?P<slot_id>\d{1,6})/$', views.non_session_edit, name='meetings_non_session_edit'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/non_session/delete/(?P<slot_id>\d{1,6})/$', views.non_session_delete, name='meetings_non_session_delete'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/rooms/$', views.rooms, name='meetings_rooms'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/select/$', views.select_group, name='meetings_select_group'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/$', views.times, name='meetings_times'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/delete/(?P<time>[0-9\:]+)/$', views.times_delete, name='meetings_times_delete'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/times/edit/(?P<time>[0-9\:]+)/$', views.times_edit, name='meetings_times_edit'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/unschedule/(?P<session_id>\d{1,6})/$', views.unschedule, name='meetings_unschedule'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<schedule_name>[A-Za-z0-9_\-]+)/(?P<acronym>[-a-z0-9]+)/schedule/$', views.schedule, name='meetings_schedule'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<acronym>[-a-z0-9]+)/remove/$', views.remove_session, name='meetings_remove_session'),
]
