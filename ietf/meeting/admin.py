# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin
from django.db.models import Count

from ietf.meeting.models import (Attended, Meeting, Room, Session, TimeSlot, Constraint, Schedule,
    SchedTimeSessAssignment, ResourceAssociation, FloorPlan, UrlResource,
    SessionPresentation, ImportantDate, SlideSubmission, SchedulingEvent, BusinessConstraint,
    ProceedingsMaterial, MeetingHost, Registration, RegistrationTicket,
    AttendanceTypeName)


class UrlResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'room', 'url', ]
    list_filter = ['name', 'room__meeting', ]
    raw_id_fields = ['room', ]
admin.site.register(UrlResource, UrlResourceAdmin)

class UrlResourceInline(admin.TabularInline):
    model = UrlResource

class RoomAdmin(admin.ModelAdmin):
    list_display = ["id", "meeting", "name", "capacity", "functional_name", "x1", "y1", "x2", "y2", ]
    list_filter = ["meeting"]
    inlines = [UrlResourceInline, ]

admin.site.register(Room, RoomAdmin)

class RoomInline(admin.TabularInline):
    model = Room

class MeetingAdmin(admin.ModelAdmin):
    list_display = ["number", "type", "date", "location", "time_zone"]
    list_filter = ["type"]
    search_fields = ["number"]
    inlines = [RoomInline]

    def location(self, instance):
        loc = []
        if instance.city:
            loc.append(instance.city)
        if instance.country:
            loc.append(instance.get_country_display())

        return ", ".join(loc)

admin.site.register(Meeting, MeetingAdmin)


class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["meeting", "type", "name", "time", "duration", "location", "session_desc"]
    list_filter = ["meeting", ]
    raw_id_fields = ["location"]
    ordering = ["-time"]

    def session_desc(self, instance):
        if instance.session:
            if instance.session.name:
                return instance.session.name
            elif instance.session.group:
                return "%s (%s)" % (instance.session.group.name, instance.session.group.acronym)

        return ""
    session_desc.short_description = "session" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(TimeSlot, TimeSlotAdmin)


class BusinessConstraintAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "penalty"]
    search_fields = ["slug", "name"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "businessconstraint" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(BusinessConstraint, BusinessConstraintAdmin)


class ConstraintAdmin(admin.ModelAdmin):
    list_display = ["meeting", "source", "name_lower", "target"]
    raw_id_fields = ["meeting", "source", "target"]
    search_fields = ["source__name", "source__acronym", "target__name", "target__acronym"]
    ordering = ["-meeting__date"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(Constraint, ConstraintAdmin)

class SchedulingEventInline(admin.TabularInline):
    model = SchedulingEvent
    raw_id_fields = ["by"]

class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "meeting", "name", "group_acronym", "purpose", "attendees", "has_onsite_tool", "chat_room", "requested", "current_status"
    ]
    list_filter = ["purpose", "meeting", ]
    raw_id_fields = ["meeting", "group", "materials", "joint_with_groups", "tombstone_for"]
    search_fields = ["meeting__number", "name", "group__name", "group__acronym", "purpose__name"]
    ordering = ["-id"]
    inlines = [SchedulingEventInline]


    def get_queryset(self, request):
        qs = super(SessionAdmin, self).get_queryset(request)
        return qs.prefetch_related('schedulingevent_set')

    def group_acronym(self, instance):
        return instance.group and instance.group.acronym

    def current_status(self, instance):
        events = sorted(instance.schedulingevent_set.all(), key=lambda e: (e.time, e.id))
        if events:
            return f'{events[-1].status} ({events[-1].time:%Y-%m-%d %H:%M})'
        else:
            return None

    def requested(self, instance):
        events = sorted(instance.schedulingevent_set.all(), key=lambda e: (e.time, e.id))
        if events:
            return events[0].time
        else:
            return None
        
    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(Session, SessionAdmin)

class SchedulingEventAdmin(admin.ModelAdmin):
    list_display = ["session", "status", "time", "by"]
    raw_id_fields = ["session", "by"]
    search_fields = ['session__name', 'session__meeting__number', 'session__group__acronym']
    ordering = ["-id"]

admin.site.register(SchedulingEvent, SchedulingEventAdmin)

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["name", "meeting", "owner", "visible", "public", "badness"]
    list_filter = ["meeting"]
    raw_id_fields = ["meeting", "owner", "origin", "base"]
    search_fields = ["meeting__number", "name", "owner__name"]
    ordering = ["-meeting", "name"]

admin.site.register(Schedule, ScheduleAdmin)


class SchedTimeSessAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "schedule", "timeslot", "session", "modified"]
    list_filter = ["timeslot__meeting", "session__group__acronym"]
    raw_id_fields = ["timeslot", "session", "schedule", "extendedfrom", ]
    search_fields = ["session__group__acronym", "schedule__name", ]

admin.site.register(SchedTimeSessAssignment, SchedTimeSessAssignmentAdmin)


class ResourceAssociationAdmin(admin.ModelAdmin):
    def used(self, instance):
        return instance.name.used
    used.boolean = True                 # type: ignore # https://github.com/python/mypy/issues/2087

    list_display = ["name", "icon", "used", "desc"]
admin.site.register(ResourceAssociation, ResourceAssociationAdmin)

class FloorPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'meeting', 'name', 'short', 'order', 'image', ]
    raw_id_fields = ['meeting', ]
admin.site.register(FloorPlan, FloorPlanAdmin)

class SessionPresentationAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'document', 'rev', 'order', ]
    list_filter = ['session__meeting', 'document__group__acronym', ]
    raw_id_fields = ['document', 'session', ]
admin.site.register(SessionPresentation, SessionPresentationAdmin)

class ImportantDateAdmin(admin.ModelAdmin):
    model = ImportantDate
    list_filter = ['meeting', ]
    list_display = ['meeting', 'name', 'date']
admin.site.register(ImportantDate,ImportantDateAdmin)

class SlideSubmissionAdmin(admin.ModelAdmin):
    model = SlideSubmission
    list_display = ['session', 'submitter', 'title']
    raw_id_fields = ['submitter', 'session', 'doc']

admin.site.register(SlideSubmission, SlideSubmissionAdmin)


class ProceedingsMaterialAdmin(admin.ModelAdmin):
    model = ProceedingsMaterial
    list_display = ['meeting', 'type', 'document']
    raw_id_fields = ['meeting', 'document']
admin.site.register(ProceedingsMaterial, ProceedingsMaterialAdmin)


class MeetingHostAdmin(admin.ModelAdmin):
    model = MeetingHost
    list_display = ['name', 'meeting']
    raw_id_fields = ['meeting']
admin.site.register(MeetingHost, MeetingHostAdmin)

class AttendedAdmin(admin.ModelAdmin):
    model = Attended
    list_display= ["id", "person", "session"]
    search_fields = ["person__name", "session__group__acronym", "session__meeting__number", "session__name", "session__purpose__name"]
    raw_id_fields= ["person", "session"]
admin.site.register(Attended, AttendedAdmin)

class MeetingFilter(admin.SimpleListFilter):
    title = 'Meeting Filter'
    parameter_name = 'meeting_id'

    def lookups(self, request, model_admin):
        # only include meetings with registration records
        meetings = Meeting.objects.filter(type='ietf').annotate(reg_count=Count('registration')).filter(reg_count__gt=0).order_by('-date')
        choices = meetings.values_list('id', 'number')
        return choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(meeting__id=self.value())
        return queryset

class AttendanceFilter(admin.SimpleListFilter):
    title = 'Attendance Type'
    parameter_name = 'attendance_type'

    def lookups(self, request, model_admin):
        choices = AttendanceTypeName.objects.all().values_list('slug', 'name')
        return choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tickets__attendance_type__slug=self.value()).distinct()
        return queryset

class RegistrationTicketInline(admin.TabularInline):
    model = RegistrationTicket

class RegistrationAdmin(admin.ModelAdmin):
    model = Registration
    list_filter = [AttendanceFilter, MeetingFilter]
    list_display = ['meeting', 'first_name', 'last_name', 'display_attendance', 'affiliation', 'country_code', 'email', ]
    search_fields = ['first_name', 'last_name', 'affiliation', 'country_code', 'email', ]
    raw_id_fields = ['person']
    inlines = [RegistrationTicketInline, ]
    ordering = ['-meeting__date', 'last_name']

    def display_attendance(self, instance):
        '''Only display the most significant ticket in the list.
        To see all the tickets inspect the individual instance
        '''
        if instance.tickets.filter(attendance_type__slug='onsite').exists():
            return 'onsite'
        elif instance.tickets.filter(attendance_type__slug='remote').exists():
            return 'remote'
        elif instance.tickets.filter(attendance_type__slug='hackathon_onsite').exists():
            return 'hackathon onsite'
        elif instance.tickets.filter(attendance_type__slug='hackathon_remote').exists():
            return 'hackathon remote'
    display_attendance.short_description = "Attendance"  # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(Registration, RegistrationAdmin)

class RegistrationTicketAdmin(admin.ModelAdmin):
    model = RegistrationTicket
    list_filter = ['attendance_type', ]
    # not available until Django 5.2, the name of a related field, using the __ notation
    # list_display = ['registration__meeting', 'registration', 'attendance_type', 'ticket_type', 'registration__email']
    # list_select_related = ('registration',)
    list_display = ['registration', 'attendance_type', 'ticket_type', 'display_meeting']
    search_fields = ['registration__first_name', 'registration__last_name', 'registration__email']
    raw_id_fields = ['registration']
    ordering = ['-registration__meeting__date', 'registration__last_name']

    def display_meeting(self, instance):
        return instance.registration.meeting.number
    display_meeting.short_description = "Meeting"  # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(RegistrationTicket, RegistrationTicketAdmin)
