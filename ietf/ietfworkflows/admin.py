from django.contrib import admin
from django.conf import settings

from ietf.ietfworkflows.models import (AnnotationTag, WGWorkflow,
                                       Stream, StreamedID)
from workflows.admin import StateInline


class AnnotationTagInline(admin.TabularInline):
    model = AnnotationTag


class IETFWorkflowAdmin(admin.ModelAdmin):
    inlines = [StateInline, AnnotationTagInline]
admin.site.register(WGWorkflow, IETFWorkflowAdmin)

class StreamedIdAdmin(admin.ModelAdmin):
    list_display = [ 'id', 'draft', 'stream', ]
    search_fields = [ 'draft__filename', ]
    raw_id_fields = [ 'draft', ]
    pass
admin.site.register(StreamedID, StreamedIdAdmin)

class StreamAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_group_attribute', 'group_chair_attribute', 'workflow_link', ]
if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    admin.site.register(Stream, StreamAdmin)
