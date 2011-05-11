#coding: utf-8
from django.contrib import admin
from ietf.proceedings.models import *
                
class IESGHistoryAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'area', 'person']
    list_filter = ['meeting', ]
    raw_id_fields = ["person", ]
admin.site.register(IESGHistory, IESGHistoryAdmin)

class MeetingAdmin(admin.ModelAdmin):
    list_display=('meeting_num', 'start_date', 'city', 'state', 'country', 'time_zone')
admin.site.register(Meeting, MeetingAdmin)

class MeetingRoomAdmin(admin.ModelAdmin):
    list_display = ['room_id', 'meeting', 'room_name']
    list_filter = ['meeting', ]
    pass
admin.site.register(MeetingRoom, MeetingRoomAdmin)

class MeetingTimeAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    pass
admin.site.register(MeetingTime, MeetingTimeAdmin)

class MeetingVenueAdmin(admin.ModelAdmin):
    list_display = [ 'meeting_num', 'break_area_name', 'reg_area_name' ]
    pass
admin.site.register(MeetingVenue, MeetingVenueAdmin)

class MinuteAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    pass
admin.site.register(Minute, MinuteAdmin)

class NonSessionAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'day', 'non_session_ref', 'time_desc', 'show_break_location', ]
    list_filter = ['meeting', ]
    pass
admin.site.register(NonSession, NonSessionAdmin)

class NonSessionRefAdmin(admin.ModelAdmin):
    pass
admin.site.register(NonSessionRef, NonSessionRefAdmin)

class SessionConflictAdmin(admin.ModelAdmin):
    pass
admin.site.register(SessionConflict, SessionConflictAdmin)

class SessionNameAdmin(admin.ModelAdmin):
    pass
admin.site.register(SessionName, SessionNameAdmin)

class SlideAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    pass
admin.site.register(Slide, SlideAdmin)

class SwitchesAdmin(admin.ModelAdmin):
    pass
admin.site.register(Switches, SwitchesAdmin)

class WgAgendaAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    pass
admin.site.register(WgAgenda, WgAgendaAdmin)

class WgMeetingSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'meeting', 'group_acronym_id', 'number_attendee', 'status', 'approval_ad', 'scheduled_date', 'last_modified_date', 'special_req', 'ad_comments']
    list_filter = ['meeting', ]
    pass
admin.site.register(WgMeetingSession, WgMeetingSessionAdmin)

class WgProceedingsActivitiesAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    pass
admin.site.register(WgProceedingsActivities, WgProceedingsActivitiesAdmin)

