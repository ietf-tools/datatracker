from django.forms import EmailInput, NumberInput, PasswordInput, RadioSelect, Textarea, TextInput, URLInput

try:
    # If Django is set up without a database, importing this widget gives RuntimeError
    from django.contrib.auth.forms import ReadOnlyPasswordHashWidget
except RuntimeError:
    ReadOnlyPasswordHashWidget = None


class RadioSelectButtonGroup(RadioSelect):
    """A RadioSelect that renders as a horizontal button group."""

    template_name = "django_bootstrap5/widgets/radio_select_button_group.html"


def is_widget_with_placeholder(widget):
    """Return whether this widget can have a placeholder."""
    return isinstance(widget, (TextInput, Textarea, NumberInput, EmailInput, URLInput, PasswordInput))
