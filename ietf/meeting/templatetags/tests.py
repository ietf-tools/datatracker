# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import debug  # pyflakes: ignore

from django.template import Context, Template
from pyquery import PyQuery

from ietf.meeting.factories import FloorPlanFactory, RoomFactory, TimeSlotFactory
from ietf.meeting.templatetags.agenda_custom_tags import AnchorNode
from ietf.name.models import ConstraintName
from ietf.utils.test_utils import TestCase


class AgendaCustomTagsTests(TestCase):
    def test_anchor_node_subclasses_implement_resolve_url(self):
        """Check that AnchorNode subclasses implement the resolve_url method

        This will only catch errors in subclasses defined in the agenda_custom_tags.py module.
        """
        for subclass in AnchorNode.__subclasses__():
            try:
                subclass.resolve_url(None, None)
            except NotImplementedError:
                self.fail(f'{subclass.__name__} must implement resolve_url() method')
            except:
                pass  # any other failure ok since we used garbage inputs

    def test_location_anchor_node(self):
        floorplan = FloorPlanFactory(meeting__type_id='ietf')
        room = RoomFactory(meeting=floorplan.meeting, floorplan=floorplan)
        context = Context({
            'no_location': TimeSlotFactory(meeting=room.meeting, location='none'),
            'no_show_location': TimeSlotFactory(meeting=room.meeting, show_location=False),
            'show_location': TimeSlotFactory(meeting=room.meeting, location=room),
        })
        template = Template("""
            {% load agenda_custom_tags %}
            <span>{% location_anchor no_location %}no_location{% end_location_anchor %}</span>
            <span>{% location_anchor no_show_location %}no_show_location{% end_location_anchor %}</span>
            <span>{% location_anchor show_location %}show_location{% end_location_anchor %}</span>
        """)
        result = template.render(context)
        self.assertInHTML('<span>no_location</span>', result)
        self.assertInHTML('<span>no_show_location</span>', result)
        self.assertInHTML(
            f'<span><a href="{context["show_location"].location.floorplan_url()}">show_location</a></span>',
            result,
        )


class EditorTagsTests(TestCase):
    def _supported_constraint_names(self):
        """Get all ConstraintNames that must be supported by the tags"""
        constraint_names = set(ConstraintName.objects.filter(used=True))
        # Instantiate a couple that are added at run-time in meeting.utils
        constraint_names.add(ConstraintName(slug='joint_with_groups', name='joint with groups'))
        constraint_names.add(ConstraintName(slug='responsible_ad', name='AD'))
        # Reversed names are also added at run-time
        reversed = [
            ConstraintName(slug=n.slug + "-reversed", name="{} - reversed".format(n.name))
            for n in constraint_names
        ]
        constraint_names.update(reversed)
        return constraint_names

    def test_constraint_icon_for(self):
        """constraint_icon_for tag should render all the necessary ConstraintNames

        Relies on ConstraintNames in the names.json fixture being up-to-date
        """
        constraint_names = self._supported_constraint_names()
        template = Template(
            '{% load editor_tags %}<html>' +
            ''.join(  # test without count param
                f'<div id="{cn.slug}">{{% constraint_icon_for {cn.slug.replace("-", "_")} %}}</div>'
                for cn in constraint_names
            ) +
            ''.join(  # test with count param
                f'<div id="{cn.slug}-count">{{% constraint_icon_for {cn.slug.replace("-", "_")} 3 %}}</div>'
                for cn in constraint_names
            ) +
            '</html>'
        )
        result = template.render(Context({cn.slug.replace('-', '_'): cn for cn in constraint_names}))
        q = PyQuery(result)
        for cn in constraint_names:
            elts = q(f'div#{cn.slug}')
            self.assertEqual(len(elts), 1)
            self.assertGreater(len(elts.html()), 0)

            elts = q(f'div#{cn.slug}-count')
            self.assertEqual(len(elts), 1)
            self.assertGreater(len(elts.html()), 0)
