# django imports
from django import template

# workflows imports
import workflows.utils

register = template.Library()

@register.inclusion_tag('workflows/transitions.html', takes_context=True)
def transitions(context, obj):
    """
    """
    request = context.get("request")
    
    return {
        "transitions" : workflows.utils.get_allowed_transitions(obj, request.user),
        "state" : workflows.utils.get_state(obj),
    }
