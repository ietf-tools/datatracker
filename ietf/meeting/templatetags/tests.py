# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.template import Context, Template

from ietf.meeting.factories import FloorPlanFactory, RoomFactory, TimeSlotFactory
from ietf.meeting.templatetags.agenda_custom_tags import AnchorNode
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
