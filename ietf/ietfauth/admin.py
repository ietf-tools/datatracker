# Copyright The IETF Trust 2025, All Rights Reserved
import datetime

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import action
from django.contrib.admin.actions import delete_selected as default_delete_selected
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone


# Replace default UserAdmin with our custom one
admin.site.unregister(User)


class AgeListFilter(admin.SimpleListFilter):
    title = "account age"
    parameter_name = "age"
    
    def lookups(self, request, model_admin):
        return [
            ("1day", "> 1 day"),
            ("3days", "> 3 days"),
            ("1week", "> 1 week"),
            ("1month", "> 1 month"),
            ("1year", "> 1 year"),
        ]

    def queryset(self, request, queryset):
        deltas = {
            "1day": datetime.timedelta(days=1),
            "3days": datetime.timedelta(days=3),
            "1week": datetime.timedelta(weeks=1),
            "1month": datetime.timedelta(days=30),
            "1year": datetime.timedelta(days=365),
        }
        if self.value():
            return queryset.filter(date_joined__lt=timezone.now()-deltas[self.value()])
        return queryset


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "person",
        "date_joined",
        "last_login",
        "is_staff",
    )
    list_filter = list(UserAdmin.list_filter) + [
        AgeListFilter,
        ("person", admin.EmptyFieldListFilter),
    ]
    actions = ["delete_selected"]

    @action(
        permissions=["delete"], description="Delete personless %(verbose_name_plural)s"
    )
    def delete_selected(self, request, queryset):
        """Delete selected action restricted to Users with a null Person field

        This displaces the default delete_selected action with a safer one that will
        only delete personless Users. It is done this way instead of by introducing
        a new action so that we can simply hand off to the default action (imported
        as default_delete_selected()) without having to adjust its template (and maybe
        other things) to make it work with a different action name.
        """
        already_confirmed = bool(request.POST.get("post"))
        personless_queryset = queryset.filter(person__isnull=True)
        original_count = queryset.count()
        personless_count = personless_queryset.count()
        if personless_count > original_count:
            # Refuse to act if the count increased!
            self.message_user(
                request,
                (
                    "Limiting the selection to Users without a Person INCREASED the "
                    "count from {} to {}. This should not happen and probably means a "
                    "concurrent change to the database affected this request. Please "
                    "try again.".format(original_count, personless_count)
                ),
                level=messages.ERROR,
            )
            return None  # return to changelist

        # Display warning/info if this is showing the confirmation page
        if not already_confirmed:
            if personless_count < original_count:
                self.message_user(
                    request,
                    (
                        "Limiting the selection to Users without a Person reduced the "
                        "count from {} to {}. Only {} will be deleted.".format(
                            original_count, personless_count, personless_count
                        )
                    ),
                    level=messages.WARNING,
                )
            else:
                self.message_user(
                    request,
                    "Confirmed that all selected Users had no Persons.",
                )

        # Django limits the number of fields in a request. The delete form itself
        # includes a few metadata fields, so give it a little padding. The default
        # limit is 1000 and everything will break if it's a small number, so not
        # bothering to check that it's > 10.
        max_count = settings.DATA_UPLOAD_MAX_NUMBER_FIELDS - 10
        if personless_count > max_count:
            self.message_user(
                request,
                (
                    f"Only {max_count} Users can be deleted at once. Will only delete "
                    f"the first {max_count} selected Personless Users."
                ),
                level=messages.WARNING,
            )
            # delete() doesn't like a queryset limited via [:max_count], so do an
            # equivalent filter.
            last_to_delete = personless_queryset.order_by("pk")[max_count]
            personless_queryset = personless_queryset.filter(pk__lt=last_to_delete.pk)

        if already_confirmed and personless_count != original_count:
            # After confirmation, none of the above filtering should change anything.
            # Refuse to delete if the DB moved underneath us.
            self.message_user(
                request,
                "Queryset count changed, nothing deleted. Please try again.",
                level=messages.ERROR,
            )
            return None

        return default_delete_selected(self, request, personless_queryset)
