# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import debug  # pyflakes: ignore

from django.template import Context, Template

from ietf.meeting.factories import FloorPlanFactory, RoomFactory, TimeSlotFactory, ConstraintFactory
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
    def test_constraint_icon_for(self):
        """constraint_icon_for tag should render properly"""
        template = Template("""
            {% load editor_tags %}
            <html>
                <div id="conflict">{% constraint_icon_for conflict %}</div>
                <div id="conflic2">{% constraint_icon_for conflic2 %}</div>
                <div id="conflic3">{% constraint_icon_for conflic3 %}</div>
                <div id="timerange">{% constraint_icon_for timerange %}</div>
                <div id="time_relation">{% constraint_icon_for time_relation %}</div>
                <div id="wg_adjacent">{% constraint_icon_for wg_adjacent %}</div>
                <div id="chair_conflict">{% constraint_icon_for chair_conflict %}</div>
                <div id="tech_overlap">{% constraint_icon_for tech_overlap %}</div>
                <div id="key_participant">{% constraint_icon_for key_participant %}</div>
                <div id="bethere-count">{% constraint_icon_for bethere_count %}</div>
                <div id="bethere-no-count">{% constraint_icon_for bethere_no_count %}</div>
            </html>
        """)

        # bethere constraint with its count filled in
        bethere_count = ConstraintFactory(name=ConstraintName.objects.get(slug='bethere'))
        bethere_count.count = 4

        def make_constraint(name_slug, **extra_attrs):
            cons = ConstraintFactory(name=ConstraintName.objects.get(slug=name_slug))
            for prop, val in extra_attrs.items():
                setattr(cons, prop, val)
            return cons

        result = template.render(Context({
            'conflict': make_constraint('conflict'),
            'conflic2': make_constraint('conflic2'),
            'conflic3': make_constraint('conflic3'),
            'timerange': make_constraint('timerange'),
            'time_relation': make_constraint('time_relation'),
            'wg_adjacent': make_constraint('wg_adjacent'),
            'chair_conflict': make_constraint('chair_conflict'),
            'tech_overlap': make_constraint('tech_overlap'),
            'key_participant': make_constraint('key_participant'),
            'bethere_count': make_constraint('bethere', count=4),
            'bethere_no_count': make_constraint('bethere'),
        }))

        self.assertInHTML('<div id="conflict"><span class="encircled">1</span></div>', result)
        self.assertInHTML('<div id="conflic2"><span class="encircled">2</span></div>', result)
        self.assertInHTML('<div id="conflic3"><span class="encircled">3</span></div>', result)
        self.assertInHTML('<div id="timerange"><i class="bi bi-calendar"></i></div>', result)
        self.assertInHTML('<div id="time_relation">&Delta;</div>', result)
        self.assertInHTML('<div id="wg_adjacent"><i class="bi bi-skip-end"></i></div>', result)
        self.assertInHTML('<div id="chair_conflict"><i class="bi bi-person-circle"></i></div>', result)
        self.assertInHTML('<div id="tech_overlap"><i class="bi bi-link"></i></div>', result)
        self.assertInHTML('<div id="key_participant"><i class="bi bi-key"></i></div>', result)
        self.assertInHTML('<div id="bethere-count"><i class="bi bi-person"></i>4</div>', result)
        self.assertInHTML('<div id="bethere-no-count"><i class="bi bi-person"></i></div>', result)
