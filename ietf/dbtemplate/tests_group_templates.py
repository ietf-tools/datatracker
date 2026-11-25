# Copyright The IETF Trust 2026, All Rights Reserved

import dataclasses
import datetime

from pyquery import PyQuery

from django.core.exceptions import ValidationError
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse

from ietf.dbtemplate.factories import DBTemplateFactory
from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.template import (TemplateValues, group_template_engine,
                                      render_group_template, value_names)
from ietf.group.factories import ReviewTeamFactory, RoleFactory
from ietf.utils.test_utils import TestCase, login_testing_unauthorized


@dataclasses.dataclass(frozen=True)
class ItemValues(TemplateValues):
    label: str

    def __str__(self):
        return self.label


@dataclasses.dataclass(frozen=True)
class ExampleValues(TemplateValues):
    title: str
    day: datetime.date | None
    items: list[ItemValues]


class GroupTemplateTests(TestCase):
    def setUp(self):
        super().setUp()
        self.team = ReviewTeamFactory(acronym="reviewteam")
        self.values = ExampleValues(
            title="A title",
            day=datetime.date(2026, 3, 4),
            items=[ItemValues(label="one"), ItemValues(label="two")],
        )

    def test_render_group_template(self):
        template = DBTemplateFactory(
            group=self.team,
            path="/group/reviewteam/example.txt",
            type_id="django",
            content=(
                "{{ title }} {{ day|date:'Y-m-d' }}"
                "{% for item in items %} {{ item }}/{{ item.label|upper }}{% endfor %}"
                " [{{ not_a_value }}]"
            ),
        )
        self.assertEqual(
            render_group_template(template, self.values),
            "A title 2026-03-04 one/ONE two/TWO []",
        )

        template.type_id = "plain"
        template.content = "$title on $day"
        self.assertEqual(render_group_template(template, self.values), "A title on 2026-03-04")

    def test_values_must_be_plain(self):
        template = DBTemplateFactory(
            group=self.team, path="/group/reviewteam/example.txt", type_id="django", content="text"
        )
        for values in (
            ExampleValues(title=self.team, day=None, items=[]),
            ExampleValues(title="A title", day=None, items=[self.team]),
            ExampleValues(title="A title", day=None, items=DBTemplate.objects.all()),
            {"title": "A title"},
        ):
            with self.assertRaises(TypeError):
                render_group_template(template, values)

    def test_group_template_engine_has_built_in_tags_only(self):
        for content in (
            "{% load ietf_filters %}",
            "{% include 'base.html' %}",
            "{% extends 'base.html' %}",
            "{% block content %}{% endblock %}",
        ):
            with self.assertRaises(TemplateSyntaxError, msg=content):
                group_template_engine.from_string(content)
        # The built-in tags and filters are there
        group_template_engine.from_string(
            "{% autoescape off %}{% for x in y %}{% ifchanged x %}{{ x|ljust:'4'|default:'-' }}"
            "{% endifchanged %}{% endfor %}{{ z|yesno:'a,b' }}{% endautoescape %}"
        )

    def test_site_loader_does_not_serve_a_group_django_template(self):
        DBTemplateFactory(
            group=self.team, path="/group/reviewteam/example.txt", type_id="django", content="for a group"
        )
        DBTemplateFactory(path="/group/defaults/example.txt", type_id="django", content="default for groups")
        DBTemplateFactory(path="/other/example.txt", type_id="django", content="not for a group")
        DBTemplateFactory(
            group=self.team, path="/group/reviewteam/plain.txt", type_id="plain", content="plain for a group"
        )
        with self.assertRaises(TemplateDoesNotExist):
            render_to_string("/group/reviewteam/example.txt")
        with self.assertRaises(TemplateDoesNotExist):
            render_to_string("/group/defaults/example.txt")
        self.assertEqual(render_to_string("/other/example.txt"), "not for a group")
        self.assertEqual(render_to_string("/group/reviewteam/plain.txt"), "plain for a group")

    def test_value_names(self):
        self.assertEqual(value_names(ExampleValues), ["title", "day", "items[]", "items[].label"])

    def test_model_clean(self):
        template = DBTemplateFactory(
            group=self.team, path="/group/reviewteam/example.txt", type_id="django", content="{{ title }}"
        )
        template.clean()
        template.content = "{% load ietf_filters %}{{ title }}"
        with self.assertRaises(ValidationError):
            template.clean()
        # The default for groups is limited in the same way
        template.group = None
        template.path = "/group/defaults/example.txt"
        with self.assertRaises(ValidationError):
            template.clean()
        # Any other template that does not belong to a group is not limited
        template.path = "/other/example.txt"
        template.clean()

    def test_edit_group_django_template(self):
        RoleFactory(group=self.team, name_id="chair", person__user__username="teamchair")
        template = DBTemplateFactory(
            group=self.team,
            path="/group/reviewteam/review/content_templates/lc.txt",
            title="Last call review",
            type_id="django",
            content="Reviewer: {{ assignment.reviewer.person.plain_name }}",
        )
        url = urlreverse(
            "ietf.dbtemplate.views.group_template_edit",
            kwargs={"acronym": self.team.acronym, "template_id": template.pk},
        )
        login_testing_unauthorized(self, "teamchair", url)

        # The page lists the names the template can use
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        names = [li.text() for li in q("#value-names li").items()]
        self.assertIn("today", names)
        self.assertIn("assignment.reviewer.person.plain_name", names)
        self.assertIn("assignment.review_request.doc.most_recent_ietflc.expires", names)

        # Content that the engine for group templates refuses is not saved
        for content in (
            "{% load ietf_filters %}Reviewer: {{ assignment.reviewer.person.plain_name }}",
            "{% include 'base.html' %}",
            "{% if assignment %}{% extends 'base.html' %}{% endif %}",
        ):
            r = self.client.post(url, {"content": content})
            self.assertEqual(r.status_code, 200, msg=content)
            self.assertTrue(PyQuery(r.content)("form .is-invalid"), msg=content)
            template.refresh_from_db()
            self.assertEqual(template.content, "Reviewer: {{ assignment.reviewer.person.plain_name }}")

        r = self.client.post(url, {"content": "Date: {{ today|date:'Y-m-d' }}"})
        self.assertEqual(r.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.content, "Date: {{ today|date:'Y-m-d' }}")

    def test_edit_page_for_other_templates_lists_no_names(self):
        RoleFactory(group=self.team, name_id="chair", person__user__username="teamchair")
        template = DBTemplateFactory(
            group=self.team,
            path="/group/reviewteam/review/content_templates/lc.txt",
            title="Last call review",
            type_id="plain",
            content="Text",
        )
        url = urlreverse(
            "ietf.dbtemplate.views.group_template_edit",
            kwargs={"acronym": self.team.acronym, "template_id": template.pk},
        )
        login_testing_unauthorized(self, "teamchair", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PyQuery(r.content)("#value-names"))
