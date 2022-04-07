# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import debug  # pyflakes: ignore

from django.template import Context, Template
from pyquery import PyQuery

from ietf.meeting.factories import FloorPlanFactory, RoomFactory, TimeSlotFactory
from ietf.meeting.templatetags.agenda_custom_tags import AnchorNode
from ietf.meeting.templatetags.editor_tags import constraint_icon_for
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
            ConstraintName(slug=f'{n.slug}-reversed', name=f'{n.name} - reversed')
            for n in constraint_names
        ]
        constraint_names.update(reversed)
        return constraint_names

    def test_constraint_icon_for_supports_all(self):
        """constraint_icon_for tag should render all the necessary ConstraintNames

        Relies on ConstraintNames in the names.json fixture being up-to-date
        """
        for cn in self._supported_constraint_names():
            self.assertGreater(len(constraint_icon_for(cn)), 0)
            self.assertGreater(len(constraint_icon_for(cn, count=1)), 0)

    def test_constraint_icon_for(self):
        """Constraint icons should render as expected

        This is the authoritative definition of what should be rendered for each constraint.
        Update this before changing the constraint_icon_for tag.
        """
        test_cases = (
            # (ConstraintName slug, additional tag parameters, expected output HTML)
            ('conflict', '', '<span class="encircled">1</span>'),
            ('conflic2', '', '<span class="encircled">2</span>'),
            ('conflic3', '', '<span class="encircled">3</span>'),
            ('conflict-reversed', '', '<span class="encircled">-1</span>'),
            ('conflic2-reversed', '', '<span class="encircled">-2</span>'),
            ('conflic3-reversed', '', '<span class="encircled">-3</span>'),
            ('bethere', '27', '<i class="bi bi-person"></i>27'),
            ('timerange', '', '<i class="bi bi-calendar"></i>'),
            ('time_relation', '', '\u0394'),  # \u0394 is a capital Greek Delta
            ('wg_adjacent', '', '<i class="bi bi-skip-end"></i>'),
            ('wg_adjacent-reversed', '', '-<i class="bi bi-skip-end"></i>'),
            ('chair_conflict', '', '<i class="bi bi-person-circle"></i>'),
            ('chair_conflict-reversed', '', '-<i class="bi bi-person-circle"></i>'),
            ('tech_overlap', '', '<i class="bi bi-link"></i>'),
            ('tech_overlap-reversed', '', '-<i class="bi bi-link"></i>'),
            ('key_participant', '', '<i class="bi bi-key"></i>'),
            ('key_participant-reversed', '', '-<i class="bi bi-key"></i>'),
            ('joint_with_groups', '', '<i class="bi bi-merge"></i>'),
            ('responsible_ad', '', '<span class="encircled">AD</span>'),
        )
        # Create a template with a cn_i context variable for the ConstraintName in each test case.
        template = Template(
            '{% load editor_tags %}<html>' +
            ''.join(
                f'<div id="test-case-{index}">{{% constraint_icon_for cn_{index} {params} %}}</div>'
                for index, (_, params, _) in enumerate(test_cases)
            ) +
            '</html>'
        )
        # Construct the cn_i in the Context and render.
        result = template.render(
            Context({
                f'cn_{index}': ConstraintName(slug=slug)
                for index, (slug, _, _) in enumerate(test_cases)
            })
        )
        q = PyQuery(result)
        for index, (slug, params, expected) in enumerate(test_cases):
            self.assertHTMLEqual(
                q(f'#test-case-{index}').html(),
                expected,
                f'Unexpected output for {slug} {params}',
            )
