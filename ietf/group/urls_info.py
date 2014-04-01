# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import patterns
from django.views.generic import RedirectView

from ietf.group import info, edit, milestones

urlpatterns = patterns('',
    (r'^$', info.active_groups),
    (r'^summary.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-area.txt', RedirectView.as_view(url='/wg/1wg-summary.txt')),
    (r'^summary-by-acronym.txt', RedirectView.as_view(url='/wg/1wg-summary-by-acronym.txt')),
    (r'^1wg-summary.txt', info.wg_summary_area),
    (r'^1wg-summary-by-acronym.txt', info.wg_summary_acronym),
    (r'^1wg-charters.txt', info.wg_charters),
    (r'^1wg-charters-by-acronym.txt', info.wg_charters_by_acronym),
    (r'^chartering/$', RedirectView.as_view(url='/group/chartering/')),
    (r'^chartering/create/$', RedirectView.as_view(url='/group/chartering/create/%(group_type)s/')),
    (r'^bofs/$', info.bofs),
    (r'^bofs/create/$', edit.edit, {'action': "create"}, "bof_create"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/documents/txt/$', info.group_documents_txt),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/$', info.group_documents, None, "group_docs"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/charter/$', info.group_charter, None, 'group_charter'),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/init-charter/', edit.submit_initial_charter),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/history/$', info.history),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/deps/dot/$', info.dependencies_dot),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/deps/pdf/$', info.dependencies_pdf),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/$', edit.edit, {'action': "edit"}, "group_edit"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/conclude/$', edit.conclude),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/$', milestones.edit_milestones, {'milestone_set': "current"}, "group_edit_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/charter/$', milestones.edit_milestones, {'milestone_set': "charter"}, "group_edit_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/milestones/charter/reset/$', milestones.reset_charter_milestones, None, "group_reset_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/ajax/searchdocs/$', milestones.ajax_search_docs, None, "group_ajax_search_docs"),
    (r'^(?P<acronym>[a-zA-Z0-9-]+)/workflow/$', edit.customize_workflow),
)
