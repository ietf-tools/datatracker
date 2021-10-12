import json
from collections import namedtuple

from django import forms

from ietf.name.models import SessionPurposeName, TimeSlotTypeName

import debug

class SessionPurposeAndTypeWidget(forms.MultiWidget):
    css_class = 'session_purpose_widget'  # class to apply to all widgets

    def __init__(self, purpose_choices, type_choices, *args, **kwargs):
        # Avoid queries on models that need to be migrated into existence - this widget is
        # instantiated during Django setup. Attempts to query, e.g., SessionPurposeName will
        # prevent migrations from running.
        widgets = (
            forms.Select(
                choices=purpose_choices,
                attrs={
                    'class': self.css_class,
                },
            ),
            forms.Select(
                choices=type_choices,
                attrs={
                    'class': self.css_class,
                    'data-allowed-options': None,
                },
            ),
        )
        super().__init__(widgets=widgets, *args, **kwargs)

    # These queryset properties are needed to propagate changes to the querysets after initialization
    # down to the widgets. The usual mechanisms in the ModelChoiceFields don't handle this for us
    # because the subwidgets are not attached to Fields in the usual way.
    @property
    def purpose_choices(self):
        return self.widgets[0].choices

    @purpose_choices.setter
    def purpose_choices(self, value):
        self.widgets[0].choices = value

    @property
    def type_choices(self):
        return self.widgets[1].choices

    @type_choices.setter
    def type_choices(self, value):
        self.widgets[1].choices = value

    def render(self, *args, **kwargs):
        # Fill in the data-allowed-options (could not do this in init because it needs to
        # query SessionPurposeName, which will break the migration if done during initialization)
        self.widgets[1].attrs['data-allowed-options'] = json.dumps(self._allowed_types())
        return super().render(*args, **kwargs)

    def decompress(self, value):
        if value:
            return [getattr(val, 'pk', val) for val in value]
        else:
            return [None, None]

    class Media:
        js = ('secr/js/session_purpose_and_type_widget.js',)

    def _allowed_types(self):
        """Map from purpose to allowed type values"""
        return {
            purpose.slug: list(purpose.timeslot_types)
            for purpose in SessionPurposeName.objects.all()
        }


class SessionPurposeAndTypeField(forms.MultiValueField):
    """Field to update Session purpose and type

    Uses SessionPurposeAndTypeWidget to coordinate setting the session purpose and type to valid
    combinations. Its value should be a tuple with (purpose, type). Its cleaned value is a
    namedtuple with purpose and value properties.
    """
    def __init__(self, purpose_queryset=None, type_queryset=None, **kwargs):
        if purpose_queryset is None:
            purpose_queryset = SessionPurposeName.objects.none()
        if type_queryset is None:
            type_queryset = TimeSlotTypeName.objects.none()
        fields = (
            forms.ModelChoiceField(queryset=purpose_queryset, label='Purpose'),
            forms.ModelChoiceField(queryset=type_queryset, label='Type'),
        )
        self.widget = SessionPurposeAndTypeWidget(*(field.choices for field in fields))
        super().__init__(fields=fields, **kwargs)

    @property
    def purpose_queryset(self):
        return self.fields[0].queryset

    @purpose_queryset.setter
    def purpose_queryset(self, value):
        self.fields[0].queryset = value
        self.widget.purpose_choices = self.fields[0].choices

    @property
    def type_queryset(self):
        return self.fields[1].queryset

    @type_queryset.setter
    def type_queryset(self, value):
        self.fields[1].queryset = value
        self.widget.type_choices = self.fields[1].choices

    def compress(self, data_list):
        # Convert data from the cleaned list from the widget into a namedtuple
        if data_list:
            compressed = namedtuple('CompressedSessionPurposeAndType', 'purpose type')
            return compressed(*data_list)
        return None

    def validate(self, value):
        # Additional validation - value has been passed through compress() already
        if value.type.pk not in value.purpose.timeslot_types:
            raise forms.ValidationError(
                '"%(type)s" is not an allowed type for the purpose "%(purpose)s"',
                params={'type': value.type, 'purpose': value.purpose},
                code='invalid_type',
            )



