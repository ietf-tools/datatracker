# Copyright The IETF Trust 2015-2022, All Rights Reserved
# -*- coding: utf-8 -*-
from pathlib import Path

from django import template
from django.conf import settings

import debug                            # pyflakes:ignore
from ietf.utils import log

register = template.Library()


class OriginNode(template.Node):
    def __init__(self, origin=None):
        # template file path if the template comes from a file:
        self.origin = origin

    def relative_path(self):
        origin_path = Path(str(self.origin))
        try:
            return origin_path.relative_to(settings.BASE_DIR)
        except ValueError:
            log.log(f'Rendering a template from outside the project root: {self.origin}')
            return '** path outside project root **'

    def render(self, context):
        if self.origin and settings.SERVER_MODE != 'production':
            return f'<!-- template: {self.relative_path()} -->'
        else:
            return ""


@register.tag('origin')
def origin_tag(parser, token):
    """Create a node indicating the path to the current template"""
    if hasattr(token, "source"):
        origin, source = token.source
        return OriginNode(origin)
    else:
        return OriginNode()
