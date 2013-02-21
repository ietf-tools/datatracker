"""
templatetags for django-form-utils

Time-stamp: <2009-03-26 12:32:08 carljm form_utils_tags.py>

"""
from django import template

from form_utils.forms import BetterForm, BetterModelForm
from form_utils.utils import select_template_from_string

register = template.Library()

@register.filter
def render(form, template_name=None):
    """
    Renders a ``django.forms.Form`` or
    ``form_utils.forms.BetterForm`` instance using a template.

    The template name(s) may be passed in as the argument to the
    filter (use commas to separate multiple template names for
    template selection).

    If not provided, the default template name is
    ``form_utils/form.html``.

    If the form object to be rendered is an instance of
    ``form_utils.forms.BetterForm`` or
    ``form_utils.forms.BetterModelForm``, the template
    ``form_utils/better_form.html`` will be used instead if present.
    
    """
    default = 'form_utils/form.html'
    if isinstance(form, (BetterForm, BetterModelForm)):
        default = ','.join(['form_utils/better_form.html', default])
    tpl = select_template_from_string(template_name or default)

    return tpl.render(template.Context({'form': form}))

        

    
