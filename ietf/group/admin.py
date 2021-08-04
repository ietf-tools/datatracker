# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import re

from functools import update_wrapper

import debug # pyflakes:ignore

from django import forms

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.core.management import load_command_class
from django.http import Http404
from django.shortcuts import render
from django.utils.encoding import force_text
from django.utils.html import escape
from django.utils.translation import ugettext as _

from ietf.group.models import (Group, GroupFeatures, GroupHistory, GroupEvent, GroupURL, GroupMilestone,
    GroupMilestoneHistory, GroupStateTransitions, Role, RoleHistory, ChangeStateGroupEvent,
    MilestoneGroupEvent, GroupExtResource, )
from ietf.name.models import GroupTypeName

from ietf.utils.validators import validate_external_resource_value
from ietf.utils.response import permission_denied

class RoleInline(admin.TabularInline):
    model = Role
    raw_id_fields = ["person", "email"]

class GroupURLInline(admin.TabularInline):
    model = GroupURL

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = '__all__'

    def clean_acronym(self):
        ''' Constrain the acronym form. Note that this doesn't look for collisions.
            See ietf.group.forms.GroupForm.clean_acronym()
        '''
        acronym = self.cleaned_data['acronym'].strip().lower()
        if not self.instance.pk:
            type = self.cleaned_data['type']
            if GroupFeatures.objects.get(type=type).has_documents:
                if not re.match(r'^[a-z][a-z0-9]+$', acronym):
                    raise forms.ValidationError("Acronym is invalid, for groups that create documents, the acronym must be at least two characters and only contain lowercase letters and numbers starting with a letter.")
            else:
                if not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', acronym):
                    raise forms.ValidationError("Acronym is invalid, must be at least two characters and only contain lowercase letters and numbers starting with a letter. It may contain hyphens, but that is discouraged.")
        return acronym

    def clean_used_roles(self):
        data = self.cleaned_data['used_roles']
        if data is None or data == '':
            raise forms.ValidationError("Must contain a valid json expression. To use the defaults prove an empty list: []")
        return data
            

class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
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
            permission_denied(request, "You don't have edit permissions for this change.")

        if obj is None:
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_text(opts.verbose_name), 'key': escape(object_id)})

        return self.send_reminder(request, sdo=obj)
    

admin.site.register(Group, GroupAdmin)


class GroupFeaturesAdminForm(forms.ModelForm):
    def clean_default_parent(self):
        # called before form clean() method -- cannot access other fields
        parent_acro = self.cleaned_data['default_parent'].strip().lower()
        if len(parent_acro) > 0:
            if Group.objects.filter(acronym=parent_acro).count() == 0:
                raise forms.ValidationError(
                    'No group exists with acronym "%(acro)s"',
                    params=dict(acro=parent_acro),
                )
        return parent_acro

    def clean(self):
        # cleaning/validation that requires multiple fields
        parent_acro = self.cleaned_data['default_parent']
        if len(parent_acro) > 0:
            parent_type = GroupTypeName.objects.filter(group__acronym=parent_acro).first()
            if parent_type not in self.cleaned_data['parent_types']:
                self.add_error(
                    'default_parent',
                    forms.ValidationError(
                        'Default parent group "%(acro)s" is type "%(gtype)s", which is not an allowed parent type.',
                        params=dict(acro=parent_acro, gtype=parent_type),
                    )
                )

class GroupFeaturesAdmin(admin.ModelAdmin):
    form = GroupFeaturesAdminForm
    list_display = [
        'type',
        'need_parent',
        'default_parent',
        'gf_parent_types',
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
        'groupman_authroles',
        'matman_roles',
        'role_order',
    ]

    def gf_parent_types(self, groupfeatures):
        """Generate list of parent types; needed because many-to-many is not handled automatically"""
        return ', '.join([gtn.slug for gtn in groupfeatures.parent_types.all()])
    gf_parent_types.short_description = 'Parent Types'   # type: ignore # https://github.com/python/mypy/issues/2087

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

class GroupExtResourceAdminForm(forms.ModelForm):
    def clean(self):
        validate_external_resource_value(self.cleaned_data['name'],self.cleaned_data['value'])

class GroupExtResourceAdmin(admin.ModelAdmin):
    form = GroupExtResourceAdminForm
    list_display = ['id', 'group', 'name', 'display_name', 'value',]
    search_fields = ['group__acronym', 'value', 'display_name', 'name__slug',]
    raw_id_fields = ['group', ]
admin.site.register(GroupExtResource, GroupExtResourceAdmin)
