from django.contrib import admin
from models import *

class MessageAdmin(admin.ModelAdmin):
    list_display = ["time", "by", "subject", "groups"]
    search_fields = ["text"]
    raw_id_fields = ["by"]

    def groups(self, instance):
        return ", ".join(g.acronym for g in related_groups.all())

admin.site.register(Message, MessageAdmin)

class SendQueueAdmin(admin.ModelAdmin):
    list_display = ["time", "by", "message", "send_at", "sent_at"]
    list_filter = ["time", "send_at", "sent_at"]
    search_fields = ["message__text"]
    raw_id_fields = ["by"]
    
admin.site.register(SendQueue, SendQueueAdmin)
