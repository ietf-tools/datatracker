from django.contrib import admin

from ietf.message.models import *

class MessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "by", "time", "groups"]
    search_fields = ["subject", "body"]
    raw_id_fields = ["by"]
    ordering = ["-time"]

    def groups(self, instance):
        return ", ".join(g.acronym for g in instance.related_groups.all())

admin.site.register(Message, MessageAdmin)

class SendQueueAdmin(admin.ModelAdmin):
    list_display = ["time", "by", "message", "send_at", "sent_at"]
    list_filter = ["time", "send_at", "sent_at"]
    search_fields = ["message__body"]
    raw_id_fields = ["by"]
    ordering = ["-time"]

admin.site.register(SendQueue, SendQueueAdmin)
