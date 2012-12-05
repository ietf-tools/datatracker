from django.contrib import admin

from ietf.dbtemplate.models import DBTemplate


class DBTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'path', 'type', 'group')
    ordering = ('path', )

admin.site.register(DBTemplate, DBTemplateAdmin)
