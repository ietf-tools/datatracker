from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template, redirect_to

urlpatterns = patterns('sec.meetings.views',
    url(r'^$', 'main', name='meetings'),
    url(r'^add/$', 'add', name='meetings_add'),
    #url(r'^blue_sheet/$', 'blue_sheet', name='meetings_blue_sheet'),
    #url(r'^clear/$', 'clear_meeting_scheduled', name='meetings_clear'),
    url(r'^(?P<meeting_id>\d{1,6})/add-tutorial/$', 'add_tutorial', name='meetings_add_tutorial'),
    url(r'^(?P<meeting_id>\d{1,6})/$', 'view', name='meetings_view'),
    url(r'^(?P<meeting_id>\d{1,6})/edit/$', 'edit_meeting',
        name='meetings_edit_meeting'),
    url(r'^(?P<meeting_id>\d{1,6})/new_session/(?P<acronym>[A-Za-z0-9_\-\+]+)/$','new_session',
        name='meetings_new_session'),
    url(r'^(?P<meeting_id>\d{1,6})/rooms/$', 'rooms', name='meetings_rooms'),
    url(r'^(?P<meeting_id>\d{1,6})/times/$', 'times', name='meetings_times'),
    url(r'^(?P<meeting_id>\d{1,6})/non_session/$', 'non_session', name='meetings_non_session'),
    url(r'^(?P<meeting_id>\d{1,6})/select/$', 'select_group',
        name='meetings_select_group'),
    url(r'^(?P<session_id>\d{1,6})/edit_session/$', 'edit_session', name='meetings_edit_session'),
    #url(r'^(?P<session_id>\d{1,6})/remove/$', 'remove_session', name='meetings_remove_session'),
)
