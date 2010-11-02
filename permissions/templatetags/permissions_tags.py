# django imports
from django import template
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.models import User, AnonymousUser

import permissions.utils
register = template.Library()

class PermissionComparisonNode(template.Node):
    """Implements a node to provide an if current user has passed permission 
    for current object.
    """
    @classmethod
    def handle_token(cls, parser, token):
        bits = token.contents.split()
        if len(bits) != 2:
            raise template.TemplateSyntaxError(
                "'%s' tag takes one argument" % bits[0])
        end_tag = 'endifhasperm'
        nodelist_true = parser.parse(('else', end_tag))
        token = parser.next_token()
        if token.contents == 'else': # there is an 'else' clause in the tag
            nodelist_false = parser.parse((end_tag,))
            parser.delete_first_token()
        else:
            nodelist_false = ""

        return cls(bits[1], nodelist_true, nodelist_false)

    def __init__(self, permission, nodelist_true, nodelist_false):
        self.permission = permission
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false

    def render(self, context):
        obj = context.get("obj")
        request = context.get("request")
        if permissions.utils.has_permission(self.permission, request.user, obj):
            return self.nodelist_true.render(context)
        else:
            return self.nodelist_false

@register.tag
def ifhasperm(parser, token):
    """This function provides functionality for the 'ifhasperm' template tag.
    """
    return PermissionComparisonNode.handle_token(parser, token)

