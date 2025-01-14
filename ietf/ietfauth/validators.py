# Copyright The IETF Trust 2024, All Rights Reserved
import re

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError


def prevent_at_symbol(name):
    if "@" in name:
        raise forms.ValidationError(
            "Please fill in name - this looks like an email address (@ is not allowed in names)."
        )


def prevent_system_name(name):
    name_without_spaces = name.replace(" ", "").replace("\t", "")
    if "(system)" in name_without_spaces.lower():
        raise forms.ValidationError("Please pick another name - this name is reserved.")


def prevent_anonymous_name(name):
    name_without_spaces = name.replace(" ", "").replace("\t", "")
    if "anonymous" in name_without_spaces.lower():
        raise forms.ValidationError("Please pick another name - this name is reserved.")


def is_allowed_address(value):
    """Validate that an address complies with datatracker requirements"""
    for pat in settings.EXCLUDED_PERSONAL_EMAIL_REGEX_PATTERNS:
        if re.search(pat, value):
            raise ValidationError(
                "This email address is not valid in a datatracker account"
            )
