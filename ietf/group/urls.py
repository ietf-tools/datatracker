# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns

urlpatterns = patterns('',
    (r'^groupmenu.json', 'ietf.group.ajax.group_menu_data', None, "group_menu_data"),
    (r'^(?P<acronym>[a-z0-9]+).json$', 'ietf.group.ajax.group_json'),
    (r'^chartering/$', 'ietf.group.info.chartering_groups'),
    (r'^chartering/create/(?P<group_type>(wg|rg))/$', 'ietf.group.edit.edit', {'action': "charter"}, "group_create"),
    (r'^concluded/$', 'ietf.group.info.concluded_groups'),
    (r'^email-aliases/$', 'ietf.group.info.email_aliases'),
    # FIXME: the things below are duplicated in urls_info.py while we
    # figure out whether to serve everything from /group/<acronym>,
    # need to unify these at some point
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/$', 'ietf.group.info.group_home', None, "group_home"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/documents/$', 'ietf.group.info.group_documents', None, "group_docs"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/charter/$', 'ietf.group.info.group_about', None, 'group_charter'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/history/$', 'ietf.group.info.history'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/deps/dot/$', 'ietf.group.info.dependencies_dot'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/deps/pdf/$', 'ietf.group.info.dependencies_pdf'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/init-charter/', 'ietf.group.edit.submit_initial_charter'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/edit/$', 'ietf.group.edit.edit', {'action': "edit"}, "group_edit"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/conclude/$', 'ietf.group.edit.conclude'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/milestones/$', 'ietf.group.milestones.edit_milestones', {'milestone_set': "current"}, "group_edit_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/milestones/charter/$', 'ietf.group.milestones.edit_milestones', {'milestone_set': "charter"}, "group_edit_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/milestones/charter/reset/$', 'ietf.group.milestones.reset_charter_milestones', None, "group_reset_charter_milestones"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/workflow/$', 'ietf.group.edit.customize_workflow'),

    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/about/(?P<group_type>.)?$', 'ietf.group.info.group_about', None, 'group_about'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/materials/$', 'ietf.group.info.materials', None, "group_materials"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/materials/new/$', 'ietf.doc.views_material.choose_material_type'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/materials/new/(?P<doc_type>[\w-]+)/$', 'ietf.doc.views_material.edit_material', { 'action': "new" }, "group_new_material"),
    (r'^(?P<acronym>[A-Za-z0-9._+-]+)/email-aliases/$', 'ietf.group.info.email_aliases'),
)


