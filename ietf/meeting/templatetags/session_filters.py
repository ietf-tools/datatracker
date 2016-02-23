from django import template

register = template.Library()

@register.filter
def presented_versions(session,doc):
   sp = session.sessionpresentation_set.filter(document=doc)
   if not sp:
       return "Document not in session"
   else:
      rev = sp.first().rev
      return rev if rev else "(current)"

@register.filter
def can_manage_materials(session,user):
    return session.can_manage_materials(user)

