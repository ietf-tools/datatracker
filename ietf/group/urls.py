# Copyright The IETF Trust 2013-2023, All Rights Reserved

from django.conf import settings
from django.urls import include
from django.views.generic import RedirectView

from ietf.community import views as community_views
from ietf.doc import views_material as material_views
from ietf.group import views, milestones as milestone_views
from ietf.utils.urls import url

# These are not used externally, only in include statements further down:
info_detail_urls = [
    url(r'^$', views.group_home),
    url(r'^documents/txt/$', views.group_documents_txt),
    url(r'^documents/$', views.group_documents),
    url(r'^documents/manage/$', community_views.manage_list),
    url(r'^documents/csv/$', community_views.export_to_csv),
    url(r'^documents/feed/$', community_views.feed),
    url(r'^documents/subscription/$', community_views.subscription),
    url(r'^charter/$', views.group_about),
    url(r'^about/$', views.group_about),
    url(r'^about/status/$', views.group_about_status),
    url(r'^about/status/edit/$', views.group_about_status_edit),
    url(r'^about/status/meeting/(?P<num>\d+)/$', views.group_about_status_meeting),
    url(r'^history/$',views.history),
    url(r'^history/addcomment/$',views.add_comment),
    url(r'^email/$', views.email),
    url(r'^deps\.json$', views.dependencies),
    url(r'^meetings/$', views.meetings),
    url(r'^edit/$', views.edit, {'action': "edit"}),
    url(r'^edit/(?P<field>[-a-z0-9_]+)/?$', views.edit, {'action': "edit"}),
    url(r'^conclude/$', views.conclude),
    url(r'^milestones/$', milestone_views.edit_milestones, {'milestone_set': "current"}, name='ietf.group.milestones.edit_milestones;current'),
    url(r'^milestones/charter/$', milestone_views.edit_milestones, {'milestone_set': "charter"}, name='ietf.group.milestones.edit_milestones;charter'),
    url(r'^milestones/charter/reset/$', milestone_views.reset_charter_milestones, None, 'ietf.group.milestones.reset_charter_milestones'),
    url(r'^workflow/$', views.customize_workflow),
    url(r'^materials/$', views.materials),
    url(r'^materials/new/$', material_views.choose_material_type),
    url(r'^materials/new/(?P<doc_type>[\w-]+)/$', material_views.edit_material, { 'action': "new" }, 'ietf.doc.views_material.edit_material'),
    url(r'^photos/$', views.group_photos),
    url(r'^reviews/$', views.review_requests),
    url(r'^reviews/manage/(?P<assignment_status>unassigned)/$', views.manage_review_requests),
    url(r'^reviews/email-assignments/$', views.email_open_review_assignments),
    url(r'^reviewers/$', views.reviewer_overview),
    url(r'^reviewers/(?P<reviewer_email>[\w%+-.@]+)/settings/$', views.change_reviewer_settings),
    url(r'^secretarysettings/$', views.change_review_secretary_settings),
    url(r'^reset_next_reviewer/$', views.reset_next_reviewer),
    url(r'^email-aliases/$', RedirectView.as_view(pattern_name=views.email,permanent=False),name='ietf.group.urls_info_details.redirect.email'),
    url(r'^statements/$', views.statements),
    url(r'^appeals/$', views.appeals),
    url(r'^appeals/artifact/(?P<artifact_id>\d+)$', views.appeal_artifact),
    url(r'^appeals/artifact/(?P<artifact_id>\d+)/markdown$', views.appeal_artifact_markdown),


]


group_urls = [
    url(r'^$', views.active_groups),
    url(r'^leadership/(?P<group_type>(wg|rg))/$', views.group_leadership),
    url(r'^leadership/(?P<group_type>(wg|rg))/csv/$', views.group_leadership_csv),
    url(r'^groupstats.json', views.group_stats_data, None, 'ietf.group.views.group_stats_data'),
    url(r'^groupmenu.json', views.group_menu_data, None, 'ietf.group.views.group_menu_data'),
    url(r'^chartering/$', views.chartering_groups),
    url(r'^chartering/create/(?P<group_type>(wg|rg))/$', views.edit, {'action': "charter"}),
    url(r'^concluded/$', views.concluded_groups),
    url(r'^email-aliases/$', views.email_aliases),
    url(r'^all-status/$', views.all_status),
    #
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.group_home),
    url(r'^%(acronym)s/' % settings.URL_REGEXPS, include(info_detail_urls)),
]


stream_urls = [
    url(r'^$', views.streams),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.stream_documents, None),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, views.stream_edit),
]


grouptype_urls = [
    url(r'^$', views.active_groups), 
    url(r'^summary.txt', RedirectView.as_view(url='/wg/1wg-summary.txt', permanent=True)),
    url(r'^summary-by-area.txt', RedirectView.as_view(url='/wg/1wg-summary.txt', permanent=True)),
    url(r'^summary-by-acronym.txt', RedirectView.as_view(url='/wg/1wg-summary-by-acronym.txt', permanent=True)),
    url(r'^1wg-summary.txt', views.wg_summary_area),
    url(r'^1wg-summary-by-acronym.txt', views.wg_summary_acronym),
    url(r'^1wg-charters.txt', views.wg_charters),
    url(r'^1wg-charters-by-acronym.txt', views.wg_charters_by_acronym),
    url(r'^chartering/$', RedirectView.as_view(url='/group/chartering/', permanent=True)),
    url(r'^chartering/create/$', RedirectView.as_view(url='/group/chartering/create/%(group_type)s/', permanent=True)),
    url(r'^bofs/$', views.bofs),
    url(r'^email-aliases/$', views.email_aliases),
    url(r'^bofs/create/$', views.edit, {'action': "create", }),
    url(r'^photos/$', views.chair_photos),
    url(r'^%(acronym)s/' % settings.URL_REGEXPS, include(info_detail_urls)),
]
