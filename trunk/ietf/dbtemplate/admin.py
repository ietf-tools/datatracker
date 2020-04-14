from django.contrib import admin

from ietf.dbtemplate.models import DBTemplate


class DBTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'path',)
    search_fields = ('title', 'path', )
    ordering = ('path', )

admin.site.register(DBTemplate, DBTemplateAdmin)
