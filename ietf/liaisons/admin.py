from django.contrib import admin

from ietf.liaisons.models import *

class LiaisonStatementAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'from_name', 'to_name', 'submitted', 'purpose', 'related_to']
    list_display_links = ['id', 'title']
    ordering = ('title', )
    raw_id_fields = ('from_contact', 'related_to', 'from_group', 'to_group', 'attachments')
admin.site.register(LiaisonStatement, LiaisonStatementAdmin)

class LiaisonDetailAdmin(admin.ModelAdmin):
    list_display = ['pk', 'title', 'from_id', 'to_body', 'submitted_date', 'purpose', 'related_to' ]
    list_display_links = ['pk', 'title']
    ordering = ('title', )
admin.site.register(LiaisonDetail, LiaisonDetailAdmin)
    