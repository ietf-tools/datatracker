from django.contrib import admin

from ietf.ietfworkflows.models import (AnnotationTag, WGWorkflow,
                                       Stream)
from workflows.admin import StateInline


class AnnotationTagInline(admin.TabularInline):
    model = AnnotationTag


class IETFWorkflowAdmin(admin.ModelAdmin):
    inlines = [StateInline, AnnotationTagInline]


admin.site.register(WGWorkflow, IETFWorkflowAdmin)
admin.site.register(Stream, admin.ModelAdmin)
