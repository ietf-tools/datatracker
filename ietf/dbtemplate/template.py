# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import string
from docutils.core import publish_string
from docutils.utils import SystemMessage
import debug                            # pyflakes:ignore

from django.template import Origin, TemplateDoesNotExist, Template as DjangoTemplate
from django.template.loaders.base import Loader as BaseLoader
from django.utils.html import format_html

from ietf.dbtemplate.models import DBTemplate
from ietf.utils.html import clean_html


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RST_TEMPLATE = os.path.join(BASE_DIR, 'resources/rst.txt')


class Template(DjangoTemplate):

    def __init__(self, template_string, origin=None, name='<Unknown Template>', engine=None):
        super(Template, self).__init__(template_string, origin, name, engine)
        self.template_string = string.Template(template_string)

    def render(self, context):
        raise NotImplementedError


class PlainTemplate(Template):

    def render(self, context):
        context_dict = {}
        for d in context.dicts:
            context_dict.update(d)
        return self.template_string.safe_substitute(context_dict)


class RSTTemplate(PlainTemplate):
    """A template written in reStructuredText, rendered to HTML

    The people who edit these are not site administrators, and the result is
    put into pages as it is. So the text cannot pull in files or URLs, cannot
    carry HTML of its own, and what comes out is cleaned like any other HTML
    that somebody typed in.
    """

    def render(self, context):
        interpolated_string = super(RSTTemplate, self).render(context)
        try:
            html = publish_string(source=interpolated_string,
                                  writer_name='html',
                                  settings_overrides={
                                      'input_encoding': 'unicode',
                                      'output_encoding': 'unicode',
                                      'embed_stylesheet': False,
                                      'xml_declaration': False,
                                      'template': RST_TEMPLATE,
                                      'halt_level': 2,
                                      # No include, csv-table from a file or URL, or raw
                                      # directives. Using one is reported as an error.
                                      'file_insertion_enabled': False,
                                      'raw_enabled': False,
                                  })
            return clean_html(html)
        except SystemMessage as e:
            args = list(e.args)
            args[0] = format_html('<div class="danger preformatted">{}</div>', args[0].replace('<string>:', 'line '))
            e.args = tuple(args)
            raise e

class Loader(BaseLoader):
    def __init__(self, engine):
        super(Loader, self).__init__(engine)
        self.is_usable = True

    def get_template(self, template_name, skip=None):
        """
        Call self.get_template_sources() and return a Template object for
        the first template matching template_name. If skip is provided, ignore
        template origins in skip. This is used to avoid recursion during
        template extending.
        """
        tried = []

        for origin in self.get_template_sources(template_name):
            if skip is not None and origin in skip:
                tried.append((origin, 'Skipped'))
                continue

            try:
                template = DBTemplate.objects.get(path=origin)
                contents = template.content
            except DBTemplate.DoesNotExist:
                tried.append((origin, 'Source does not exist'))
                continue
            else:
                if   template.type_id == 'rst':
                    return RSTTemplate(contents, origin, origin.template_name, self.engine)
                elif template.type_id == 'plain':
                    return PlainTemplate(contents, origin, origin.template_name, self.engine)
                elif template.type_id == 'django':
                    return DjangoTemplate(contents, origin, origin.template_name, self.engine)
                else:
                    return Template(contents, origin, origin.template_name, self.engine)

        raise TemplateDoesNotExist(template_name, tried=tried)

    def get_template_sources(self, template_name):
        for template in DBTemplate.objects.filter(path__endswith=template_name):
            yield Origin(
                name=template.path,
                template_name=template_name,
                loader=self,
            )

