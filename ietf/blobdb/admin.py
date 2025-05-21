# Copyright The IETF Trust 2025, All Rights Reserved
from django.contrib import admin
from django.db.models.functions import Length
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import Blob


@admin.register(Blob)
class BlobAdmin(admin.ModelAdmin):
    list_display = ["bucket", "name", "object_size", "modified", "mtime", "content_type"]
    list_filter = [
        "bucket",
        "content_type",
        ("modified", DateRangeQuickSelectListFilterBuilder()),
        ("mtime", DateRangeQuickSelectListFilterBuilder()),
    ]
    search_fields = ["name"]
    list_display_links = ["name"]

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .defer("content")  # don't load this unless we want it
            .annotate(object_size=Length("content"))  # accessed via object_size()
        )

    @admin.display(ordering="object_size")
    def object_size(self, instance):
        """Get the size of the object"""
        return instance.object_size  # annotation added in get_queryset()
