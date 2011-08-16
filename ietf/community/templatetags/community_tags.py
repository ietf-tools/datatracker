from django import template

from ietf.community.models import CommunityList
from redesign.group.models import Role


register = template.Library()


class CommunityListNode(template.Node):
    
    def __init__(self, user, var_name):
        self.user = user
        self.var_name = var_name

    def render(self, context):
        user = self.user.resolve(context)
        if not user or not user.is_authenticated():
            return ''
        lists = {'personal': CommunityList.objects.get_or_create(user=user)[0]}
        try:
            person = user.get_profile()
            groups = []
            managed_areas = [i.group for i in Role.objects.filter(name__slug='ad', email__in=person.email_set.all())]
            groups += list(CommunityList.objects.filter(group__in=managed_areas))
            managed_wg = [i.group for i in Role.objects.filter(name__slug='chair', group__type__slug='wg', email__in=person.email_set.all())]
            groups += list(CommunityList.objects.filter(group__in=managed_wg))
            lists['group'] = groups
        except:
            pass
        context.update({self.var_name: lists})
        return ''


@register.tag
def get_user_managed_lists(parser, token):
    firstbits = token.contents.split(None, 2)
    if len(firstbits) != 3:
        raise TemplateSyntaxError("'get_user_managed_lists' tag takes three arguments")
    user = parser.compile_filter(firstbits[1])
    lastbits_reversed = firstbits[2][::-1].split(None, 2)
    if lastbits_reversed[1][::-1] != 'as':
        raise TemplateSyntaxError("next-to-last argument to 'get_user_managed_lists' tag must"
                                  " be 'as'")
    var_name = lastbits_reversed[0][::-1]
    return CommunityListNode(user, var_name)
