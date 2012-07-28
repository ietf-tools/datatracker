from django import template

register = template.Library()

@register.filter
def rfc_editor_state(doc):
   state = doc.states.filter(type='draft-stream-ise')
   return state[0] if state else None
