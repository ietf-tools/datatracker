#coding: utf-8
from django import template
from django.contrib import admin
from django.contrib.admin.util import unquote
from django.core.exceptions import PermissionDenied
from django.core.management import load_command_class
from django.http import Http404
from django.shortcuts import render_to_response
from django.utils.encoding import force_unicode
from django.utils.functional import update_wrapper
from django.utils.html import escape
from django.utils.translation import ugettext as _

from ietf.liaisons.models import (FromBodies, LiaisonDetail, LiaisonPurpose,
                                  SDOs, LiaisonManagers, SDOAuthorizedIndividual)
from ietf.ietfauth.models import LegacyWgPassword, LegacyLiaisonUser


class FromBodiesAdmin(admin.ModelAdmin):
    list_display = ['body_name', 'contact_link', 'other_sdo']
admin.site.register(FromBodies, FromBodiesAdmin)


class LiaisonDetailAdmin(admin.ModelAdmin):
    list_display = ['detail_id', 'title', 'legacy_from_body', 'to_body', 'submitted_date', 'purpose', 'related_to']
    ordering = ('title', )
#     fields = ('title', 'body','submitted_date', 'last_modified_date', 'to_email', 'cc1', 'cc2', 'to_poc',
#               'response_contact', 'technical_contact', 'purpose', 'purpose_text', 'deadline_date', 'action_taken',
#               'related_to')
    raw_id_fields=['person', 'related_to']
admin.site.register(LiaisonDetail, LiaisonDetailAdmin)


class LiaisonPurposeAdmin(admin.ModelAdmin):
    ordering = ('purpose_text', )
admin.site.register(LiaisonPurpose, LiaisonPurposeAdmin)


class LiaisonManagersAdmin(admin.ModelAdmin):
    list_display = ['id', '__unicode__', 'person_link', 'user_name', 'groups', 'sdo_link', ]
    ordering = ('person__first_name', 'person__last_name' )
#    fields = ('person', 'sdo')
    raw_id_fields=['person']
admin.site.register(LiaisonManagers, LiaisonManagersAdmin)


class LiaisonManagersInline(admin.TabularInline):
    model = LiaisonManagers
    raw_id_fields=['person']

class SDOAuthorizedIndividualInline(admin.TabularInline):
    model = SDOAuthorizedIndividual
    raw_id_fields=['person']

class SDOsAdmin(admin.ModelAdmin):
    list_display = ['sdo_id', 'sdo_name', 'liaisonmanager_link', 'sdo_contact_link']
    inlines = [LiaisonManagersInline, SDOAuthorizedIndividualInline]

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
        urls += super(SDOsAdmin, self).get_urls()
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
        return render_to_response('admin/liaisons/sdos/send_reminder.html',
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
admin.site.register(SDOs, SDOsAdmin)


class SDOAuthorizedIndividualAdmin(admin.ModelAdmin):
    list_display = ['id', 'person_link', 'user_name', 'groups', 'sdo_link']
    raw_id_fields=['person']
admin.site.register(SDOAuthorizedIndividual, SDOAuthorizedIndividualAdmin)


class LegacyWgPasswordAdmin(admin.ModelAdmin):
    list_display = ['pk', 'person_link', 'login_name', ]
admin.site.register(LegacyWgPassword, LegacyWgPasswordAdmin)


class LegacyLiaisonUserAdmin(admin.ModelAdmin):
    list_display = ['pk', 'person_link', 'login_name', 'user_level', 'comment', ]
admin.site.register(LegacyLiaisonUser, LegacyLiaisonUserAdmin)
