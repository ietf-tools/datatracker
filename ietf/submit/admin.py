# Copyright The IETF Trust 2011-2020, All Rights Reserved
from django.urls import reverse as urlreverse
from django.contrib import admin
from django.conf import settings
from django import forms

from ietf.submit.models import (Preapproval, Submission, SubmissionEvent, 
    SubmissionCheck, SubmissionEmailEvent, SubmissionExtResource)
from ietf.utils.validators import validate_external_resource_value


class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'rev', 'draft_link', 'status_link', 'submission_date',]
    list_filter = ['state', ]
    ordering = [ '-id' ]
    search_fields = ['name', ]
    raw_id_fields = ['group', 'draft']

    def status_link(self, instance):
        url = urlreverse('ietf.submit.views.submission_status',
                         kwargs=dict(submission_id=instance.pk,
                                     access_token=instance.access_token()))
        return '<a href="%s">%s</a>' % (url, instance.state)
    status_link.allow_tags = True       # type: ignore # https://github.com/python/mypy/issues/2087

    def draft_link(self, instance):
        if instance.state_id == "posted":
            return '<a href="%s/%s-%s.txt">%s</a>' % (settings.IETF_ID_ARCHIVE_URL,instance.name, instance.rev, instance.name)
        else:
            return instance.name
    draft_link.allow_tags = True        # type: ignore # https://github.com/python/mypy/issues/2087
admin.site.register(Submission, SubmissionAdmin)

class SubmissionEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'rev', 'time', 'by', 'desc', ]
    raw_id_fields = ['submission', 'by']
    search_fields = ['submission__name']
    def rev(self, instance):
        return instance.submission.rev
admin.site.register(SubmissionEvent, SubmissionEventAdmin)

class SubmissionCheckAdmin(admin.ModelAdmin):
    list_display = ['submission', 'time', 'checker', 'passed', 'errors', 'warnings', 'message']
    raw_id_fields = ['submission']
    search_fields = ['submission__name']
admin.site.register(SubmissionCheck, SubmissionCheckAdmin)

class PreapprovalAdmin(admin.ModelAdmin):
    pass
admin.site.register(Preapproval, PreapprovalAdmin)

class SubmissionEmailEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'time', 'by', 'message', 'desc', ]
admin.site.register(SubmissionEmailEvent, SubmissionEmailEventAdmin)

class SubmissionExtResourceAdminForm(forms.ModelForm):
    def clean(self):
        validate_external_resource_value(self.cleaned_data['name'],self.cleaned_data['value'])

class SubmissionExtResourceAdmin(admin.ModelAdmin):
    form = SubmissionExtResourceAdminForm
    list_display = ['id', 'submission', 'name', 'display_name', 'value',]
    search_fields = ['submission__name', 'value', 'display_name', 'name__slug',]
    raw_id_fields = ['submission', ]
admin.site.register(SubmissionExtResource, SubmissionExtResourceAdmin)
