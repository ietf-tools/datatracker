# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from functools import update_wrapper

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.core.management import load_command_class
from django.http import Http404
from django.shortcuts import render
from django.utils.encoding import force_text
from django.utils.html import escape
from django.utils.translation import ugettext as _

from ietf.group.models import (Group, GroupFeatures, GroupHistory, GroupEvent, GroupURL, GroupMilestone,
    GroupMilestoneHistory, GroupStateTransitions, Role, RoleHistory, ChangeStateGroupEvent,
    MilestoneGroupEvent, )

class RoleInline(admin.TabularInline):
    model = Role
    raw_id_fields = ["person", "email"]

class GroupURLInline(admin.TabularInline):
    model = GroupURL

class GroupAdmin(admin.ModelAdmin):
    list_display = ["acronym", "name", "type", "state", "time", "role_list"]
    list_display_links = ["acronym", "name"]
    list_filter = ["type", "state", "time"]
    search_fields = ["acronym", "name"]
    ordering = ["name"]
    raw_id_fields = ["charter", "parent"]
    inlines = [RoleInline, GroupURLInline]
    prepopulated_fields = {"acronym": ("name", )}

    def role_list(self, obj):
        roles = Role.objects.filter(group=obj).order_by("name", "person__name").select_related('person')
        res = []
        for r in roles:
            res.append('<a href="../../person/person/%s/">%s</a> (<a href="../../group/role/%s/">%s)' % (r.person.pk, escape(r.person.plain_name()), r.pk, r.name.name))
        return ", ".join(res)
    role_list.short_description = "Persons" # type: ignore # https://github.com/python/mypy/issues/2087
    role_list.allow_tags = True         # type: ignore     # https://github.com/python/mypy/issues/2087
    

    # SDO reminder
    def get_urls(self):
        from ietf.utils.urls import url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urls = [
            url(r'^reminder/$', wrap(self.send_reminder), name='%s_%s_reminder' % info),
            url(r'^(.+)/reminder/$', wrap(self.send_one_reminder), name='%s_%s_one_reminder' % info),
        ]
        urls += super(GroupAdmin, self).get_urls()
        return urls

    def send_reminder(self, request, sdo=None):
        opts = self.model._meta
        app_label = opts.app_label

        output = None
        sdo_pk = sdo and sdo.pk or None
        if request.method == 'POST' and request.POST.get('send', False):
            command = load_command_class('ietf.liaisons', 'remind_update_sdo_list')
            output=command.handle(return_output=True, sdo_pk=sdo_pk)
            output='\n'.join(output)

        context = {
            'opts': opts,
            'has_change_permission': self.has_change_permission(request),
            'app_label': app_label,
            'output': output,
            'sdo': sdo,
            }
        return render(request, 'admin/group/group/send_sdo_reminder.html', context )


    def send_one_reminder(self, request, object_id):
        model = self.model
        opts = model._meta

        try:
            obj = self.queryset(request).get(pk=unquote(object_id))
        except model.DoesNotExist:
            obj = None

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_text(opts.verbose_name), 'key': escape(object_id)})

        return self.send_reminder(request, sdo=obj)
    

admin.site.register(Group, GroupAdmin)

class GroupFeaturesAdmin(admin.ModelAdmin):
    list_display = [

        'type',
        'has_milestones',
        'has_chartering_process',
        'has_documents',
        'has_session_materials',
        'has_nonsession_materials',
        'has_meetings',
        'has_reviews',
        'has_default_jabber',
        'acts_like_wg',
        'create_wiki',
        'custom_group_roles',
        'customize_workflow',
        'is_schedulable',
        'show_on_agenda',
        'req_subm_approval',
        'agenda_type',
        'material_types',
        'admin_roles',
        'docman_roles',
        'groupman_roles',
        'matman_roles',
        'role_order',

    ]
admin.site.register(GroupFeatures, GroupFeaturesAdmin)

class GroupHistoryAdmin(admin.ModelAdmin):
    list_display = ["time", "acronym", "name", "type"]
    list_display_links = ["acronym", "name"]
    list_filter = ["type"]
    search_fields = ["acronym", "name"]
    ordering = ["name"]
    raw_id_fields = ["group", "parent"]

admin.site.register(GroupHistory, GroupHistoryAdmin)

class GroupURLAdmin(admin.ModelAdmin):
    list_display = ['id', 'group', 'name', 'url']
    raw_id_fields = ['group']
    search_fields = ['name']
admin.site.register(GroupURL, GroupURLAdmin)

class GroupMilestoneAdmin(admin.ModelAdmin):
    list_display = ["group", "desc", "due", "resolved", "time"]
    search_fields = ["group__name", "group__acronym", "desc", "resolved"]
    raw_id_fields = ["group", "docs"]
admin.site.register(GroupMilestone, GroupMilestoneAdmin)
admin.site.register(GroupMilestoneHistory, GroupMilestoneAdmin)

class GroupStateTransitionsAdmin(admin.ModelAdmin):
    list_display = ['id', 'group', 'state']
    raw_id_fields = ['group', 'state']
admin.site.register(GroupStateTransitions, GroupStateTransitionsAdmin)

class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "person", "email", "group"]
    list_display_links = ["name"]
    search_fields = ["name__name", "person__name", "email__address"]
    list_filter = ["name", "group"]
    ordering = ["id"]
    raw_id_fields = ["email", "person", "group"]
admin.site.register(Role, RoleAdmin)
admin.site.register(RoleHistory, RoleAdmin)

class GroupEventAdmin(admin.ModelAdmin):
    list_display = ["id", "group", "time", "type", "by", ]
    search_fields = ["group__name", "group__acronym"]
admin.site.register(GroupEvent, GroupEventAdmin)

class ChangeStateGroupEventAdmin(admin.ModelAdmin):
    list_display = ["id", "group", "state", "time", "type", "by", ]
    list_filter = ["state", "time", ]
    search_fields = ["group__name", "group__acronym"]
admin.site.register(ChangeStateGroupEvent, ChangeStateGroupEventAdmin)

class MilestoneGroupEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'group', 'time', 'type', 'by', 'desc', 'milestone']
    list_filter = ['time']
    raw_id_fields = ['group', 'by', 'milestone']
admin.site.register(MilestoneGroupEvent, MilestoneGroupEventAdmin)
