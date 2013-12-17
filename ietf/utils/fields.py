from django import forms
from django.core.validators import validate_email, ValidationError


class MultiEmailField(forms.CharField):
    widget = forms.widgets.Textarea

    def clean(self, value):
        super(MultiEmailField, self).clean(value)
        if not value:
            return value

        if value.endswith(','):
            value = value[:-1]
        emails = [v.strip() for v in value.split(',') if v.strip()]

        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError("This is not a valid comma separated email list.")

        return value
