from django.conf import settings
from django import template

from ietf.ietfworkflows.utils import get_state_for_draft
from ietf.wgchairs.accounts import (can_manage_workflow_in_group,
                                    can_manage_delegates_in_group,
                                    can_manage_shepherds_in_group)


register = template.Library()


@register.inclusion_tag('wgchairs/wgchairs_admin_options.html', takes_context=True)
def wgchairs_admin_options(context, wg):
    request = context.get('request', None)
    user = request and request.user
    return {'user': user,
            'can_manage_delegates': can_manage_delegates_in_group(user, wg),
            'can_manage_workflow': can_manage_workflow_in_group(user, wg),
            'can_manage_shepherds': can_manage_shepherds_in_group(user, wg),
            'wg': wg,
            'selected': context.get('selected', None),
           }

@register.simple_tag
def writeup(doc):
    writeup = doc.protowriteup_set.all()
    if not writeup:
        return ''
    else:
        return writeup[0].writeup


@register.simple_tag
def writeupdate(doc):
    writeup = doc.protowriteup_set.all()
    if not writeup:
        return ''
    else:
        return writeup[0].date


@register.inclusion_tag('wgchairs/draft_state.html', takes_context=True)
def show_state(context, doc):
    return {'doc': doc,
            'state': get_state_for_draft(doc),
           }
