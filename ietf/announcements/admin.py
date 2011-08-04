#coding: utf-8
from django.contrib import admin
from django.conf import settings
from ietf.announcements.models import *
                
class AnnouncedFromAdmin(admin.ModelAdmin):
    pass
admin.site.register(AnnouncedFrom, AnnouncedFromAdmin)

class AnnouncedToAdmin(admin.ModelAdmin):
    pass
admin.site.register(AnnouncedTo, AnnouncedToAdmin)

class AnnouncementAdmin(admin.ModelAdmin):
    list_display=('announced_from', 'announced_to', 'announced_date', 'subject')
    date_hierarchy='announced_date'
    list_filter=['nomcom', 'manually_added']
    raw_id_fields=['announced_by']
admin.site.register(Announcement, AnnouncementAdmin)

class ScheduledAnnouncementAdmin(admin.ModelAdmin):
    pass
admin.site.register(ScheduledAnnouncement, ScheduledAnnouncementAdmin)


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    class MessageAdmin(admin.ModelAdmin):
        list_display = ["time", "by", "subject", "groups"]
        search_fields = ["body"]
        raw_id_fields = ["by"]

        def groups(self, instance):
            return ", ".join(g.acronym for g in related_groups.all())

    admin.site.register(Message, MessageAdmin)

    class SendQueueAdmin(admin.ModelAdmin):
        list_display = ["time", "by", "message", "send_at", "sent_at"]
        list_filter = ["time", "send_at", "sent_at"]
        search_fields = ["message__body"]
        raw_id_fields = ["by"]

    admin.site.register(SendQueue, SendQueueAdmin)
