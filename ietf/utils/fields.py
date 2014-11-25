from django import forms
from django.core.validators import validate_email

class MultiEmailField(forms.Field):
    def to_python(self, value):
        "Normalize data to a list of strings."

        # Return an empty list if no input was given.
        if not value:
            return []

        if isinstance(value, basestring):
            values = value.split(',')
            return [ x.strip() for x in values if x.strip() ]
        else:
            return value

    def validate(self, value):
        "Check if value consists only of valid emails."

        # Use the parent's handling of required fields, etc.
        super(MultiEmailField, self).validate(value)

        for email in value:
            validate_email(email)

def yyyymmdd_to_strftime_format(fmt):
    return (fmt
            .replace("yyyy", "%Y")
            .replace("yy", "%y")
            .replace("mm", "%m")
            .replace("m", "%-m")
            .replace("MM", "%B")
            .replace("M", "%b")
            .replace("dd", "%d")
            .replace("d", "%-d")
            .replace("MM", "%A")
            .replace("M", "%a")
    )

class DatepickerDateField(forms.DateField):
    """DateField with some glue for triggering JS Bootstrap datepicker."""

    def __init__(self, date_format, picker_settings={}, *args, **kwargs):
        strftime_format = yyyymmdd_to_strftime_format(date_format)
        kwargs["input_formats"] = [strftime_format]
        kwargs["widget"] = forms.DateInput(format=strftime_format)
        super(DatepickerDateField, self).__init__(*args, **kwargs)

        self.widget.attrs["data-provide"] = "datepicker"
        self.widget.attrs["data-date-format"] = date_format
        for k, v in picker_settings.iteritems():
            self.widget.attrs["data-date-%s" % k] = v
