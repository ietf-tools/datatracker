from django.contrib import admin
from models import *
from person.models import *

class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['name']
    raw_id_fields = ['authors', 'related', 'group', 'shepherd', 'ad']
admin.site.register(Document, DocumentAdmin)

class DocHistoryAdmin(admin.ModelAdmin):
    list_display = ['doc', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['doc__name']
    ordering = ['time', 'doc', 'rev']
    raw_id_fields = ['doc', 'authors', 'related', 'group', 'shepherd', 'ad']
admin.site.register(DocHistory, DocHistoryAdmin)

class DocAliasAdmin(admin.ModelAdmin):
    list_display = [ 'name', 'document_link', ]
    search_fields = [ 'name', 'document__name', ]
    raw_id_fields = ['document']
admin.site.register(DocAlias, DocAliasAdmin)


# events

class DocEventAdmin(admin.ModelAdmin):
    list_display = ["doc", "type", "by_raw", "time"]
    raw_id_fields = ["doc", "by"]

    def by_raw(self, instance):
        return instance.by_id
    by_raw.short_description = "By"
    
admin.site.register(DocEvent, DocEventAdmin)

admin.site.register(NewRevisionDocEvent, DocEventAdmin)
admin.site.register(WriteupDocEvent, DocEventAdmin)
admin.site.register(StatusDateDocEvent, DocEventAdmin)
admin.site.register(LastCallDocEvent, DocEventAdmin)
admin.site.register(TelechatDocEvent, DocEventAdmin)

class BallotPositionDocEventAdmin(DocEventAdmin):
    raw_id_fields = ["doc", "by", "ad"]

admin.site.register(BallotPositionDocEvent, BallotPositionDocEventAdmin)
    
