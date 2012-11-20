from django import forms
from django.forms.util import ValidationError
from django.core.validators import email_re


class MultiEmailField(forms.CharField):
    widget = forms.widgets.Textarea

    def clean(self, value):
        super(MultiEmailField, self).clean(value)
        if value:
            emails = map(unicode.strip, value.split(','))
        else:
            return value

        for email in emails:
            if not email_re.match(email):
                raise ValidationError("This is not a valid comma separated email list.")

        return value
