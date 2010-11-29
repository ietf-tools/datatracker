from django import template

from ietf.wgchairs.accounts import (can_manage_workflow_in_group,
                                    can_manage_delegates_in_group)


register = template.Library()


@register.inclusion_tag('wgchairs/wgchairs_admin_options.html', takes_context=True)
def wgchairs_admin_options(context, wg):
    request = context.get('request', None)
    user = request and request.user
    return {'user': user,
            'can_manage_delegates': can_manage_delegates_in_group(user, wg),
            'can_manage_workflow': can_manage_workflow_in_group(user, wg),
            'wg': wg,
            'selected': context.get('selected', None),
           }
