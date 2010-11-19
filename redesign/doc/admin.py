from django.contrib import admin
from models import *
from person.models import *

class RelatedDocAdmin(admin.ModelAdmin):
    list_display = ["source", "relationship", "target"]
    search_fields = ["doc_alias__name", "related_document_set__name", ]
    list_display_links = ["relationship", ]
admin.site.register(RelatedDoc, RelatedDocAdmin)    

class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['name']
    raw_id_fields = ['authors', 'related', 'group', 'shepherd', 'ad']
admin.site.register(Document, DocumentAdmin)

class DocHistoryAdmin(admin.ModelAdmin):
    list_display = ['doc', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['doc__name']
    ordering = ['time', 'doc', 'rev']
    raw_id_fields = ['authors', 'related']
admin.site.register(DocHistory, DocHistoryAdmin)

class DocAliasAdmin(admin.ModelAdmin):
    list_display = [ 'name', 'document_link', ]
    search_fields = [ 'name', 'document__name', ]
admin.site.register(DocAlias, DocAliasAdmin)

class SendQueueAdmin(admin.ModelAdmin):
    pass
admin.site.register(SendQueue, SendQueueAdmin)


# events

class EventAdmin(admin.ModelAdmin):
    raw_id_fields = ["doc", "by"]
admin.site.register(Event, EventAdmin)

admin.site.register(Message, EventAdmin)
admin.site.register(Text, EventAdmin)
admin.site.register(BallotPosition, EventAdmin)
admin.site.register(Expiration, EventAdmin)
admin.site.register(Telechat, EventAdmin)

