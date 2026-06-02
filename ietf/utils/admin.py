# Copyright The IETF Trust 2011-2026, All Rights Reserved


from django.contrib import admin
from .models import DumpInfo, DirtyBits


class SaferStackedInline(admin.StackedInline):
    """StackedInline without delete by default"""

    can_delete = False  # no delete button
    show_change_link = True  # show a link to the resource (where it can be deleted)


class SaferTabularInline(admin.TabularInline):
    """TabularInline without delete by default"""

    can_delete = False  # no delete button
    show_change_link = True  # show a link to the resource (where it can be deleted)


@admin.register(DumpInfo)
class DumpInfoAdmin(admin.ModelAdmin):
    list_display = ["date", "host", "tz"]
    list_filter = ["date"]


@admin.register(DirtyBits)
class DirtyBitsAdmin(admin.ModelAdmin):
    list_display = ["slug", "dirty_time", "processed_time"]
