# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import patterns, include
from django.views.generic import RedirectView

from ietf.wginfo import views, edit, milestones

urlpatterns = patterns('',
    (r'^$', views.active_wgs),
    (r'^summary.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-area.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-acronym.txt', RedirectView.as_view(url='/wg/1wg-summary-by-acronym.txt')),
    (r'^1wg-summary.txt', views.wg_summary_area),
    (r'^1wg-summary-by-acronym.txt', views.wg_summary_acronym),
    (r'^1wg-charters.txt', views.wg_charters),
    (r'^1wg-charters-by-acronym.txt', views.wg_charters_by_acronym),
    (r'^chartering/$', views.chartering_wgs),
    (r'^bofs/$', views.bofs),
    (r'^chartering/create/$', edit.edit, {'action': "charter"}, "wg_create"),
    (r'^bofs/create/$', edit.edit, {'action': "create"}, "bof_create"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/documents/txt/$', views.group_documents_txt),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/$', views.group_documents, None, "wg_docs"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/charter/$', views.group_charter, None, 'group_charter'),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/init-charter/', edit.submit_initial_charter, None, "wg_init_charter"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/history/$', views.history),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/$', edit.edit, {'action': "edit"}, "group_edit"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/conclude/$', edit.conclude, None, "wg_conclude"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/$', milestones.edit_milestones, {'milestone_set': "current"}, "wg_edit_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/charter/$', milestones.edit_milestones, {'milestone_set': "charter"}, "wg_edit_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/charter/reset/$', milestones.reset_charter_milestones, None, "wg_reset_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/ajax/searchdocs/$', milestones.ajax_search_docs, None, "wg_ajax_search_docs"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/workflow/$', edit.customize_workflow),
)
