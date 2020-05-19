# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import simple_history

from django.contrib import admin

from ietf.review.models import (ReviewerSettings, ReviewSecretarySettings, UnavailablePeriod,
    ReviewWish, NextReviewerInTeam, ReviewRequest, ReviewAssignment, ReviewTeamSettings )

class ReviewerSettingsAdmin(simple_history.admin.SimpleHistoryAdmin):
    def acronym(self, obj):
        return obj.team.acronym
    list_display = ['id', 'person', 'acronym', 'min_interval', 'filter_re', 'remind_days_before_deadline', ]
    list_filter = ["team"]
    search_fields = ["person__name"]
    ordering = ["-id"]
    raw_id_fields = ["team", "person"]

admin.site.register(ReviewerSettings, ReviewerSettingsAdmin)

class ReviewSecretarySettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'team', 'person', 'remind_days_before_deadline', 'max_items_to_show_in_reviewer_list', 'days_to_show_in_reviewer_list']
    raw_id_fields = ['team', 'person']
admin.site.register(ReviewSecretarySettings, ReviewSecretarySettingsAdmin)

class UnavailablePeriodAdmin(simple_history.admin.SimpleHistoryAdmin):
    list_display = ["person", "team", "start_date", "end_date", "availability", "reason"]
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

class NextReviewerInTeamAdmin(admin.ModelAdmin):
    list_display = ["team", "next_reviewer"]
    list_display_links = ["team"]
    ordering = ["team"]
    raw_id_fields = ["team", "next_reviewer"]

admin.site.register(NextReviewerInTeam, NextReviewerInTeamAdmin)

class ReviewRequestAdmin(simple_history.admin.SimpleHistoryAdmin):
    list_display = ["doc", "time", "type", "team", "deadline"]
    list_display_links = ["doc"]
    list_filter = ["team", "type", "state"]
    ordering = ["-id"]
    raw_id_fields = ["doc", "team", "requested_by"]
    date_hierarchy = "time"
    search_fields = ["doc__name"]

admin.site.register(ReviewRequest, ReviewRequestAdmin)

class ReviewAssignmentAdmin(simple_history.admin.SimpleHistoryAdmin):
    list_display = ["review_request", "reviewer", "assigned_on", "result"]
    list_filter = ["result", "state"]
    ordering = ["-id"]
    raw_id_fields = ["review_request", "reviewer", "result", "review"]
    search_fields = ["review_request__doc__name"]

admin.site.register(ReviewAssignment, ReviewAssignmentAdmin)

class ReviewTeamSettingsAdmin(admin.ModelAdmin):
    list_display = ["group", ] 
    search_fields = ["group__acronym", ]
    raw_id_fields = ["group", ]
    filter_horizontal = ["review_types", "review_results", "notify_ad_when"]

admin.site.register(ReviewTeamSettings, ReviewTeamSettingsAdmin)
