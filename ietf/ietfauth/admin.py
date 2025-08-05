# Copyright The IETF Trust 2025, All Rights Reserved
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import action
from django.contrib.admin.actions import delete_selected as default_delete_selected
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User


# Replace default UserAdmin with our custom one
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_filter = UserAdmin.list_filter + (("person", admin.EmptyFieldListFilter),)
    actions = (UserAdmin.actions or ()) + ("delete_selected",)

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
        personless_queryset = queryset.filter(person__isnull=True)
        original_count = queryset.count()
        personless_count = personless_queryset.count()
        if personless_count > original_count:
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
            return
        elif personless_count < original_count:
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
                request, "Confirmed that all selected Users had no Persons."
            )

        # Django limits the number of fields in a request. The delete form itself
        # includes a few metadata fields, so give it a little padding. The default
        # limit is 1000 and everything will break if it's a small number, so not
        # bothering to check that it's > 10.
        max_count = settings.DATA_UPLOAD_MAX_NUMBER_FIELDS - 10
        personless_queryset = personless_queryset.order_by("pk")[:max_count]
        if personless_count > max_count:
            self.message_user(
                request,
                (
                    f"Only {max_count} Users can be deleted at once. Will only delete "
                    f"the first {max_count} selected Personless Users."
                ),
                level=messages.WARNING,
            )
        return default_delete_selected(self, request, personless_queryset)
