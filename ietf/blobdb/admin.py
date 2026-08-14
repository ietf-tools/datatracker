# Copyright The IETF Trust 2025-2026, All Rights Reserved
from django.contrib import admin
from django.db.models import QuerySet
from django.db.models.functions import Length
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .apps import get_blobdb
from .models import Blob, ResolvedMaterial
from .utils import queue_for_replication


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
    actions = ["replicate_blob"]

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

    @admin.action(description="Replicate blobs")
    def replicate_blob(self, request, queryset: QuerySet[Blob]):
        blob_count = 0
        for blob in queryset.all():
            if isinstance(blob, Blob):
                queue_for_replication(
                    bucket=blob.bucket, name=blob.name, using=get_blobdb()
                )
                blob_count += 1
        self.message_user(
            request,
            f"Queued replication of a total of {blob_count} Blob(s)",
        )


@admin.register(ResolvedMaterial)
class ResolvedMaterialAdmin(admin.ModelAdmin):
    model = ResolvedMaterial
    list_display = ["name", "meeting_number", "bucket", "blob"]
    list_filter = ["meeting_number", "bucket"]
    search_fields = ["name", "blob"]
    ordering = ["name"]
