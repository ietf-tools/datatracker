from django import forms
from django.forms import ValidationError
#from django.core.exceptions import ValidationError
from django.utils.encoding import smart_unicode
#from django.core.validators import validate_email

import re

class MultiEmailField(forms.Field):
    def to_python(self, value):
        "Normalize data to a list of strings."

        # Return an empty list if no input was given.
        if not value:
            return []
        return value.split(',')

    def validate(self, value):
        "Check if value consists only of valid emails."
        assert False, ('got to validate', value)
        # Use the parent's handling of required fields, etc.
        super(MultiEmailField, self).validate(value)

        for email in value:
            validate_email(email)
