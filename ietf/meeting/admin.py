from django.contrib import admin

from ietf.meeting.models import Meeting, Room, Session, TimeSlot, Constraint, Schedule, SchedTimeSessAssignment, ResourceAssociation

class RoomAdmin(admin.ModelAdmin):
    list_display = ["id", "meeting", "name", "capacity", ]
    list_filter = ["meeting"]
    ordering = ["-meeting"]

admin.site.register(Room, RoomAdmin)

class RoomInline(admin.TabularInline):
    model = Room

class MeetingAdmin(admin.ModelAdmin):
    list_display = ["number", "type", "date", "location", "time_zone"]
    list_filter = ["type"]
    search_fields = ["number"]
    ordering = ["-date"]
    inlines = [RoomInline]

    def location(self, instance):
        loc = []
        if instance.city:
            loc.append(instance.city)
        if instance.country:
            loc.append(instance.get_country_display())

        return u", ".join(loc)

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
                return u"%s (%s)" % (instance.session.group.name, instance.session.group.acronym)

        return ""
    session_desc.short_description = "session"

admin.site.register(TimeSlot, TimeSlotAdmin)


class ConstraintAdmin(admin.ModelAdmin):
    list_display = ["meeting", "source", "name_lower", "target"]
    raw_id_fields = ["meeting", "source", "target"]
    search_fields = ["source__name", "source__acronym", "target__name", "target__acronym"]
    ordering = ["-meeting__date"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name"

admin.site.register(Constraint, ConstraintAdmin)

class SessionAdmin(admin.ModelAdmin):
    list_display = ["meeting", "name", "group", "attendees", "requested", "status"]
    list_filter = ["meeting", ]
    raw_id_fields = ["meeting", "group", "requested_by", "materials"]
    search_fields = ["meeting__number", "name", "group__name"]
    ordering = ["-requested"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name"

admin.site.register(Session, SessionAdmin)

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["name", "meeting", "owner", "visible", "public", "badness"]
    list_filter = ["meeting", ]
    raw_id_fields = ["meeting", "owner", ]
    search_fields = ["meeting__number", "name", "owner__name"]
    ordering = ["meeting", "name"]

admin.site.register(Schedule, ScheduleAdmin)


class SchedTimeSessAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "schedule", "timeslot", "session", "modified"]
    list_filter = ["timeslot__meeting", "schedule"]
    raw_id_fields = ["timeslot", "session", "schedule", "extendedfrom", ]

admin.site.register(SchedTimeSessAssignment, SchedTimeSessAssignmentAdmin)


class ResourceAssociationAdmin(admin.ModelAdmin):
    list_display = ["desc", "icon", "desc", ]
admin.site.register(ResourceAssociation, ResourceAssociationAdmin)
