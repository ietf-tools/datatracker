from django.contrib import admin

from ietf.ietfworkflows.models import (AnnotationTag, WGWorkflow,
                                       Stream, StreamedID)
from workflows.admin import StateInline


class AnnotationTagInline(admin.TabularInline):
    model = AnnotationTag


class IETFWorkflowAdmin(admin.ModelAdmin):
    inlines = [StateInline, AnnotationTagInline]
admin.site.register(WGWorkflow, IETFWorkflowAdmin)

class StreamedIdAdmin(admin.ModelAdmin):
    list_display = [ 'id', 'draft', 'stream', 'content_type', 'content_id', 'group', ]
    search_fields = [ 'draft__filename', ]
    raw_id_fields = [ 'draft', ]
    pass
admin.site.register(StreamedID, StreamedIdAdmin)

class StreamAdmin(admin.ModelAdmin):
    list_display = ['name', 'with_groups', 'group_model', 'group_chair_model', 'workflow_link', ]
admin.site.register(Stream, StreamAdmin)
