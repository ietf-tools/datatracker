from django.contrib import admin
from django import template
from django.utils.functional import update_wrapper
from django.contrib.admin.util import unquote
from django.core.exceptions import PermissionDenied
from django.core.management import load_command_class
from django.http import Http404
from django.shortcuts import render_to_response
from django.utils.encoding import force_unicode
from django.utils.functional import update_wrapper
from django.utils.html import escape
from django.utils.translation import ugettext as _

from ietf.group.models import *

class RoleInline(admin.TabularInline):
    model = Role
    raw_id_fields = ["person", "email"]

class GroupURLInline(admin.TabularInline):
    model = GroupURL

class GroupAdmin(admin.ModelAdmin):
    list_display = ["acronym", "name", "type", "role_list"]
    list_display_links = ["acronym", "name"]
    list_filter = ["type"]
    search_fields = ["acronym", "name"]
    ordering = ["name"]
    raw_id_fields = ["charter", "parent", "ad"]
    inlines = [RoleInline, GroupURLInline]
    prepopulated_fields = {"acronym": ("name", )}

    def role_list(self, obj):
        roles = Role.objects.filter(group=obj).order_by("name", "person__name").select_related('person')
        res = []
        for r in roles:
            res.append(u'<a href="../../person/person/%s/">%s</a> (<a href="../../group/role/%s/">%s)' % (r.person.pk, escape(r.person.plain_name()), r.pk, r.name.name))
        return ", ".join(res)
    role_list.short_description = "Persons"
    role_list.allow_tags = True
    

    # SDO reminder
    def get_urls(self):
        from django.conf.urls.defaults import patterns, url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.module_name

        urls = patterns('',
            url(r'^reminder/$',
                wrap(self.send_reminder),
                name='%s_%s_reminder' % info),
            url(r'^(.+)/reminder/$',
                wrap(self.send_one_reminder),
                name='%s_%s_one_reminder' % info),
            )
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
        return render_to_response('admin/group/group/send_sdo_reminder.html',
                                  context,
                                  context_instance = template.RequestContext(request, current_app=self.admin_site.name),
                                 )

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
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_unicode(opts.verbose_name), 'key': escape(object_id)})

        return self.send_reminder(request, sdo=obj)
    

admin.site.register(Group, GroupAdmin)

class GroupHistoryAdmin(admin.ModelAdmin):
    list_display = ["acronym", "name", "type"]
    list_display_links = ["acronym", "name"]
    list_filter = ["type"]
    search_fields = ["acronym", "name"]
    ordering = ["name"]
    raw_id_fields = ["group", "parent", "ad"]

admin.site.register(GroupHistory, GroupHistoryAdmin)

class GroupMilestoneAdmin(admin.ModelAdmin):
    list_display = ["group", "desc", "expected_due_date", "time"]
    search_fields = ["group__name", "group__acronym", "desc"]
    raw_id_fields = ["group"]

admin.site.register(GroupMilestone, GroupMilestoneAdmin)

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
    search_fields = ["group__name", "group__acronym"]
admin.site.register(ChangeStateGroupEvent, ChangeStateGroupEventAdmin)

