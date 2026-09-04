# Copyright The IETF Trust 2026, All Rights Reserved
from django import forms
from django.contrib import admin, messages
from django.db import IntegrityError, transaction
from django.utils.html import format_html

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
            token_hash = AppApiToken.hash(new_token)
            existing = AppApiToken.objects.filter(token=token_hash)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    "This token value is already in use. Enter a different value."
                )
        return new_token


@admin.register(AppApiToken)
class AppApiTokenAdmin(admin.ModelAdmin):
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
        if new_token or not change:
            # Not change => this is a new instance. Give it a default if a token
            # was not specified.
            if not new_token:
                new_token = AppApiToken.generate_token()
            obj.set_token(new_token)
        try:
            # Nested atomic() is a savepoint, so a collision here only rolls back
            # this save, not the whole request-level transaction the admin already
            # wraps this view in.
            with transaction.atomic():
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


@admin.register(KnownApiEndpoint)
class KnownApiEndpointAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled"]
    search_fields = ["name"]
