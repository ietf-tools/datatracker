# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import dataclasses
import datetime
import os
import string
import types
import typing
from docutils.core import publish_string
from docutils.utils import SystemMessage
import debug                            # pyflakes:ignore

from django.template import Context, Engine, Origin, TemplateDoesNotExist, Template as DjangoTemplate
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

def is_group_template(template):
    """True for a template that belongs to a group, and for the default of one.

    The defaults are the templates under /group/defaults/. They belong to no
    group and are used for a group that does not have a template of its own.
    """
    return template.group_id is not None or template.path.startswith("/group/defaults/")


class GroupTemplateEngine(Engine):
    """Template engine for a group template of type "django".

    The chairs of the group can edit such a template. It gets the built-in
    tags and filters and nothing else:

    - There are no tag libraries, so {% load %} is refused.
    - {% include %}, {% extends %} and {% block %} do not exist.
    - There are no template loaders and no context processors.
    """

    default_builtins = [
        "django.template.defaulttags",
        "django.template.defaultfilters",
    ]


group_template_engine = GroupTemplateEngine(loaders=[])


class TemplateValues:
    """Base class for the values given to a group template.

    A subclass is a frozen dataclass. A field holds text, a number, a date,
    None, another TemplateValues, or a list of these. A field never holds a
    model object: a template can follow relations from a model object to
    data that the people who edit the template are not allowed to see.
    """


PLAIN_TYPES = (str, int, float, type(None), datetime.date, datetime.time)


def check_plain_values(value, name):
    """Raise TypeError unless value is made only of the types listed above."""
    if isinstance(value, PLAIN_TYPES):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            check_plain_values(item, f"{name}[]")
    elif isinstance(value, TemplateValues):
        for field in dataclasses.fields(value):
            check_plain_values(getattr(value, field.name), f"{name}.{field.name}")
    else:
        raise TypeError(
            f"{name} is a {type(value).__name__}. "
            "A group template is given plain values only."
        )


def render_group_template(template, values):
    """Render a group template and return the text.

    values is a TemplateValues. The names of its fields are the names the
    template can use.
    """
    check_plain_values(values, "values")
    context = Context(
        {field.name: getattr(values, field.name) for field in dataclasses.fields(values)}
    )
    if template.type_id == "django":
        return group_template_engine.from_string(template.content).render(context)
    elif template.type_id == "rst":
        return RSTTemplate(template.content).render(context)
    else:
        return PlainTemplate(template.content).render(context)


def value_names(values_class, prefix=""):
    """List the names a template can use when it is given a values_class.

    A name that holds a list ends in "[]".
    """
    names = []
    for name, hint in typing.get_type_hints(values_class).items():
        if typing.get_origin(hint) in (typing.Union, types.UnionType):
            # "X | None" is listed as X
            hint = next(h for h in typing.get_args(hint) if h is not type(None))
        if typing.get_origin(hint) is list:
            name += "[]"
            hint = typing.get_args(hint)[0]
        names.append(prefix + name)
        if isinstance(hint, type) and issubclass(hint, TemplateValues):
            names.extend(value_names(hint, prefix + name + "."))
    return names


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
                    if is_group_template(template):
                        # The chairs of the group can edit this template.
                        # It is not given the tags, filters and context of
                        # this engine. See render_group_template().
                        tried.append((origin, 'Is a group template'))
                        continue
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

