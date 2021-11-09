# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-

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
