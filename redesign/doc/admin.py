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

class SendQueueAdmin(admin.ModelAdmin):
    pass
admin.site.register(SendQueue, SendQueueAdmin)


# events

class EventAdmin(admin.ModelAdmin):
    list_display = ["doc", "type", "by_raw", "time"]
    raw_id_fields = ["doc", "by"]

    def by_raw(self, instance):
        return instance.by_id
    by_raw.short_description = "By"
    
admin.site.register(Event, EventAdmin)

admin.site.register(Message, EventAdmin)
admin.site.register(Text, EventAdmin)
admin.site.register(NewRevision, EventAdmin)
admin.site.register(Status, EventAdmin)
admin.site.register(Expiration, EventAdmin)
admin.site.register(Telechat, EventAdmin)

class BallotPositionAdmin(EventAdmin):
    raw_id_fields = ["doc", "by", "ad"]

admin.site.register(BallotPosition, BallotPositionAdmin)
    
