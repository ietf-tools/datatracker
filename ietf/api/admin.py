# Copyright The IETF Trust 2026, All Rights Reserved
from django import forms
from django.contrib import admin, messages
from django.db import IntegrityError, transaction
from django.utils.html import format_html

from ietf.api.ietf_utils import cached_hashed_token_store
from ietf.api.models import AppApiToken, KnownApiEndpoint


class KnownApiEndpointInline(admin.TabularInline):
    model = AppApiToken.endpoints.through
    raw_id_fields = ["knownapiendpoint"]
    verbose_name = "API Endpoint"


class AppApiTokenForm(forms.ModelForm):
    # Not named "token" to avoid interaction with the model field. Conversion is done by
    # save_model() below.
    new_token = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"size": "60"}),
        help_text=(
            "Enter a value to set a new token. Leave blank to keep the current "
            "token (when editing) or auto-generate one (when creating)."
        ),
    )

    class Meta:
        model = AppApiToken
        fields = ["client", "description", "enabled"]

    def clean_new_token(self):
        new_token = self.cleaned_data["new_token"]
        if new_token:
            try:
                self.instance.validate_new_token(new_token)
            except ValueError as err:
                raise forms.ValidationError(f"{str(err)} Enter a different value.")
        elif self.instance.pk is None:
            # New instance without a specified token, generate a default
            new_token = AppApiToken.generate_token()
        return new_token


class TokenCacheRefreshMixin:
    """Refresh the API token cache after admin changes, inside the transaction

    The refresh is done in save_related() rather than save_model() because the
    admin persists inline formsets and M2M fields (e.g. AppApiToken.endpoints)
    only after save_model() returns. Both run inside the transaction that
    Django opens around the change view, so a failed refresh rolls back the
    object and its related rows together.

    Deletes are covered by delete_model() (the delete view) and delete_queryset()
    (the delete_selected changelist action, currently disabled site-wide in
    ietf/urls.py). Django does not open a transaction around changelist actions,
    so each hook here opens its own to keep the rollback guarantee on that path.

    The delete_queryset() method is here as a safeguard in case delete-selected is
    later enabled and is not covered by tests. Someone enabling that action should
    add appropriate test coverage.
    """

    def _refresh_token_cache(self, request):
        try:
            cached_hashed_token_store(force_update=True)
        except Exception:
            self.message_user(
                request,
                "Change failed. The cached API tokens being enforced may not agree "
                "with the database state. Edit and save again to update the cache. "
                "Alert the admins if this message appears again.",
                level=messages.ERROR,
            )
            raise

    def save_related(self, request, form, formsets, change):
        with transaction.atomic():
            super().save_related(request, form, formsets, change)
            self._refresh_token_cache(request)

    def delete_model(self, request, obj):
        with transaction.atomic():
            super().delete_model(request, obj)
            self._refresh_token_cache(request)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            super().delete_queryset(request, queryset)
            self._refresh_token_cache(request)


@admin.register(AppApiToken)
class AppApiTokenAdmin(TokenCacheRefreshMixin, admin.ModelAdmin):
    form = AppApiTokenForm
    list_display = ["__str__", "enabled", "description"]
    list_filter = ["enabled", "endpoints__name"]
    search_fields = ["client", "description"]
    inlines = [KnownApiEndpointInline]
    fields = ["client", "description", "enabled", "new_token"]
    exclude = ["endpoints"]

    class Media:
        js = ["ietf/js/api/admin-token-copy.js"]

    def save_model(self, request, obj: AppApiToken, form, change):
        new_token = form.cleaned_data["new_token"]
        if new_token:
            obj.set_token(new_token)
        try:
            super().save_model(request, obj, form, change)
        except IntegrityError:
            self.message_user(
                request,
                "This token value collided with one saved by another request "
                "just now and was not saved. Edit the object again and try a "
                "different value.",
                level=messages.ERROR,
            )
            raise

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Only reveal the new token once the save and cache refresh have succeeded
        new_token = form.cleaned_data["new_token"]
        if new_token:
            self.message_user(
                request,
                format_html(
                    "New API token (this will not be shown again): "
                    '<span class="copy-token">'
                    '<input type="text" readonly size="60" value="{}">  '
                    '<button type="button" class="button">Copy to clipboard</button>'
                    "</span>",
                    new_token,
                ),
                level=messages.WARNING,
            )

    def get_search_results(self, request, queryset, search_term):
        # call the standard search on search_fields
        standard_search_qs, _ = super().get_search_results(
            request, queryset, search_term
        )
        # also search for the token
        hashed_search_term = AppApiToken.hash(search_term.strip())
        matching_token_qs = queryset.filter(token=hashed_search_term)
        return standard_search_qs | matching_token_qs, True


@admin.register(KnownApiEndpoint)
class KnownApiEndpointAdmin(TokenCacheRefreshMixin, admin.ModelAdmin):
    list_display = ["name", "enabled"]
    search_fields = ["name"]
