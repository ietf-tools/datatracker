#coding: utf-8
from django.contrib import admin
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

