from django.conf.urls.defaults import *
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.views.generic.simple import direct_to_template, redirect_to
from django.views.generic import list_detail

urlpatterns = patterns('sec.proceedings.views',
    url(r'^$', 'main', name='proceedings'),
    url(r'^(?P<id>\d{1,6})/$', 'view', name='proceedings_view'),
    #url(r'^(?P<meeting_id>\d{1,6})/convert/$', 'convert', name='proceedings_convert'),
    #url(r'^(?P<id>\d{1,6})/(?P<slide_id>\d{1,6})/upload_presentation/$', 
    #    'upload_presentation', name='proceedings_upload_presentation'),
    #url(r'^(?P<id>\d{1,6})/status/$', 'status'),
    #url(r'^(?P<id>\d{1,6})/status/modify/$', 'modify'),
    url(r'^(?P<meeting_id>\d{1,6})/select/$', 'select', name='proceedings_select'),
    url(r'^(?P<meeting_id>\d{1,6})/select/(?P<group_id>-?\d{1,6})/$',
        'upload_unified', name='proceedings_upload_unified'),
    url(r'^delete/(?P<meeting_id>\d{1,6})/(?P<group_id>-?\d{1,6})/(?P<type>(slide|minute|agenda))/(?P<object_id>[A-Za-z0-9._\-\+]+)/$',
        'delete_material', name='proceedings_delete_material'),
    # interim stuff
    url(r'^interim/$', 'select_interim', name='proceedings_select_interim'),
    #url(r'^interim/(?P<group_id>-?\d{1,6})/$', 'interim', name='proceedings_interim'),
    #url(r'^interim/(?P<meeting_id>\d{1,6})/delete/$', 'delete_interim_meeting',
    #    name='proceedings_delete_interim_meeting'),
    #url(r'^interim/directory/$', 'interim_directory', name='proceedings_interim_directory'),
    #url(r'^interim/directory/(?P<sortby>(group|date))/$', 'interim_directory',
    #    name='proceedings_interim_directory_sort'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<group_id>-?\d{1,6})/(?P<slide_id>[A-Za-z0-9._\-\+]+)/$',
        'edit_slide', name='proceedings_edit_slide'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<group_id>-?\d{1,6})/(?P<slide_id>[A-Za-z0-9._\-\+]+)/replace/$',
        'replace_slide', name='proceedings_replace_slide'),
    url(r'^(?P<meeting_id>\d{1,6})/(?P<group_id>-?\d{1,6})/(?P<slide_id>[A-Za-z0-9._\-\+]+)/(?P<direction>(up|down))/$',
        'move_slide', name='proceedings_move_slide'),
)
