from django.conf.urls.defaults import *
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.views.generic.simple import direct_to_template, redirect_to
from django.views.generic import list_detail

urlpatterns = patterns('sec.proceedings.views',
    url(r'^$', 'main', name='proceedings'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/$', 'select', name='proceedings_select'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<session_id>\d{1,6})/$',
        'upload_unified', name='proceedings_upload_unified'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<acronym>[A-Za-z0-9_\-\+]+)/$',
        'upload_unified', name='proceedings_upload_unified'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<name>[A-Za-z0-9._\-\+]+)/delete/$',
        'delete_material', name='proceedings_delete_material'),
    # interim stuff
    url(r'^interim/$', 'select_interim', name='proceedings_select_interim'),
    url(r'^interim/(?P<meeting_num>interim-\d{4}-[A-Za-z0-9_\-\+]+)/delete/$', 'delete_interim_meeting',
        name='proceedings_delete_interim_meeting'),
    url(r'^interim/(?P<meeting_num>interim-\d{4}-[A-Za-z0-9_\-\+]+)/build-proc/$', 'build_proc',
        name='proceedings_build_proc'),
    url(r'^interim/(?P<acronym>[A-Za-z0-9_\-\+]+)/$', 'interim', name='proceedings_interim'),
    #url(r'^interim/directory/$', 'interim_directory', name='proceedings_interim_directory'),
    #url(r'^interim/directory/(?P<sortby>(group|date))/$', 'interim_directory',
    #    name='proceedings_interim_directory_sort'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<slide_id>[A-Za-z0-9._\-\+]+)/$',
        'edit_slide', name='proceedings_edit_slide'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<slide_id>[A-Za-z0-9._\-\+]+)/replace/$',
        'replace_slide', name='proceedings_replace_slide'),
    url(r'^(?P<meeting_num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<slide_id>[A-Za-z0-9._\-\+]+)/(?P<direction>(up|down))/$',
        'move_slide', name='proceedings_move_slide'),
)
