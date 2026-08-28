# Copyright The IETF Trust 2026, All Rights Reserved
from django.contrib import admin

from ietf.api.models import AppApiToken, KnownApiEndpoint


class KnownApiEndpointInline(admin.TabularInline):
    model = AppApiToken.endpoints.through
    raw_id_fields = ["knownapiendpoint"]
    verbose_name = "API Endpoint"


@admin.register(AppApiToken)
class AppApiTokenAdmin(admin.ModelAdmin):
    list_display = ["__str__", "enabled", "description"]
    list_filter = ["enabled", "endpoints__name"]
    search_fields = ["client", "description", "token"]
    inlines = [KnownApiEndpointInline]
    exclude = ["endpoints"]


@admin.register(KnownApiEndpoint)
class KnownApiEndpointAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled"]
    search_fields = ["name"]
