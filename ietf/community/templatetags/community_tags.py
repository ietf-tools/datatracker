from django import template
from django.template.loader import render_to_string
from django.conf import settings

register = template.Library()

@register.inclusion_tag('community/display_field.html', takes_context=False)
def show_field(field, doc):
    return {'field': field,
            'value': field.get_value(doc),
           }


@register.simple_tag
def get_clist_view(clist):
    if settings.DEBUG or not clist.cached:
        clist.cached = render_to_string('community/raw_view.html', {
                'cl': clist,
                'dc': clist.get_display_config()
            })
        clist.save()
        return clist.cached
