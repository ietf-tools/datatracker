from django.contrib import admin

from ietf.message.models import Message, MessageAttachment, SendQueue, AnnouncementFrom

class MessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "by", "time", "groups"]
    search_fields = ["subject", "body"]
    raw_id_fields = ["by", "related_groups", "related_docs"]
    ordering = ["-time"]

    def groups(self, instance):
        return ", ".join(g.acronym for g in instance.related_groups.all())
admin.site.register(Message, MessageAdmin)

class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'message', 'filename', 'removed',]
    raw_id_fields = ['message']
admin.site.register(MessageAttachment, MessageAttachmentAdmin)

class SendQueueAdmin(admin.ModelAdmin):
    list_display = ["time", "by", "message", "send_at", "sent_at"]
    list_filter = ["time", "send_at", "sent_at"]
    search_fields = ["message__body"]
    raw_id_fields = ["by", "message"]
    ordering = ["-time"]
admin.site.register(SendQueue, SendQueueAdmin)

class AnnouncementFromAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'address', ]
admin.site.register(AnnouncementFrom, AnnouncementFromAdmin)


