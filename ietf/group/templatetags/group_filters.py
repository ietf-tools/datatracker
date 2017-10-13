from django import template

register = template.Library()

@register.filter
def has_sessions(group,num):
    return group.session_set.filter(meeting__number=num).exists()

@register.filter
def active_roles(queryset):
    return queryset.filter(state_id='active').exclude(group__acronym='secretariat')
    
