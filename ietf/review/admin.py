from django.contrib import admin

from ietf.review.models import (ReviewerSettings, UnavailablePeriod, ReviewWish,
                                ResultUsedInReviewTeam, TypeUsedInReviewTeam, NextReviewerInTeam,
                                ReviewRequest)

class ReviewerSettingsAdmin(admin.ModelAdmin):
    list_filter = ["team"]
    search_fields = ["person__name"]
    ordering = ["-id"]
    raw_id_fields = ["team", "person"]

admin.site.register(ReviewerSettings, ReviewerSettingsAdmin)

class UnavailablePeriodAdmin(admin.ModelAdmin):
    list_display = ["person", "team", "start_date", "end_date", "availability"]
    list_display_links = ["person"]
    list_filter = ["team"]
    date_hierarchy = "start_date"
    search_fields = ["person__name"]
    ordering = ["-id"]
    raw_id_fields = ["team", "person"]

admin.site.register(UnavailablePeriod, UnavailablePeriodAdmin)

class ReviewWishAdmin(admin.ModelAdmin):
    list_display = ["person", "team", "doc"]
    list_display_links = ["person"]
    list_filter = ["team"]
    search_fields = ["person__name"]
    ordering = ["-id"]
    raw_id_fields = ["team", "person", "doc"]

admin.site.register(ReviewWish, ReviewWishAdmin)

class ResultUsedInReviewTeamAdmin(admin.ModelAdmin):
    list_display = ["team", "result"]
    list_display_links = ["team"]
    list_filter = ["team"]
    ordering = ["team", "result__order"]
    raw_id_fields = ["team"]

admin.site.register(ResultUsedInReviewTeam, ResultUsedInReviewTeamAdmin)

class TypeUsedInReviewTeamAdmin(admin.ModelAdmin):
    list_display = ["team", "type"]
    list_display_links = ["team"]
    list_filter = ["team"]
    ordering = ["team", "type__order"]
    raw_id_fields = ["team"]

admin.site.register(TypeUsedInReviewTeam, TypeUsedInReviewTeamAdmin)

class NextReviewerInTeamAdmin(admin.ModelAdmin):
    list_display = ["team", "next_reviewer"]
    list_display_links = ["team"]
    ordering = ["team"]
    raw_id_fields = ["team", "next_reviewer"]

admin.site.register(NextReviewerInTeam, NextReviewerInTeamAdmin)

class ReviewRequestAdmin(admin.ModelAdmin):
    list_display = ["doc", "time", "type", "team", "deadline"]
    list_display_links = ["doc"]
    list_filter = ["team", "type", "state", "result"]
    ordering = ["-id"]
    raw_id_fields = ["doc", "team", "requested_by", "reviewer", "review"]
    date_hierarchy = "time"
    search_fields = ["doc__name", "reviewer__person__name"]

admin.site.register(ReviewRequest, ReviewRequestAdmin)
