# Copyright The IETF Trust 2025, All Rights Reserved
from ietf.liaisons.forms import flatten_choices
from ietf.utils.test_utils import TestCase


class HelperTests(TestCase):
    def test_choices_from_group_queryset(self):
        raise NotImplementedError()

    def test_all_internal_groups(self):
        raise NotImplementedError()

    def test_internal_groups_for_person(self):
        raise NotImplementedError()

    def test_external_groups_for_person(self):
        raise NotImplementedError()

    def test_flatten_choices(self):
        self.assertEqual(flatten_choices([]), [])
        self.assertEqual(
            flatten_choices(
                (
                    ("group A", ()),
                    ("group B", (("val0", "label0"), ("val1", "label1"))),
                    ("group C", (("val2", "label2"),)),
                )
            ),
            [("val0", "label0"), ("val1", "label1"), ("val2", "label2")],
        )


class IncomingLiaisonFormTests(TestCase):
    pass


class OutgoingLiaisonFormTests(TestCase):
    pass


class EditLiaisonFormTests(TestCase):
    pass
