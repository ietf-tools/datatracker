from django.contrib import admin

from ietf.ietfworkflows.models import (AnnotationTag, WGWorkflow,
                                       Stream, StreamedID)
from workflows.admin import StateInline


class AnnotationTagInline(admin.TabularInline):
    model = AnnotationTag


class IETFWorkflowAdmin(admin.ModelAdmin):
    inlines = [StateInline, AnnotationTagInline]

class StreamedIdAdmin(admin.ModelAdmin):
    list_display = [ 'id', 'draft', 'stream', 'content_type', 'content_id', 'group', ]
    search_fields = [ 'draft__filename', ]
    pass
admin.site.register(StreamedID, StreamedIdAdmin)

admin.site.register(WGWorkflow, IETFWorkflowAdmin)
admin.site.register(Stream, admin.ModelAdmin)
