# Copyright The IETF Trust 2025, All Rights Reserved
from ietf.group.factories import GroupFactory
from ietf.group.models import Group
from ietf.liaisons.forms import flatten_choices, choices_from_group_queryset
from ietf.utils.test_utils import TestCase


class HelperTests(TestCase):
    @staticmethod
    def _alphabetically_by_acronym(group_list):
        return sorted(group_list, key=lambda item: item.acronym)

    def test_choices_from_group_queryset(self):
        main_groups = list(Group.objects.filter(acronym__in=["ietf", "iab"]))
        areas = GroupFactory.create_batch(2, type_id="area")
        wgs = GroupFactory.create_batch(2)

        # No groups
        self.assertEqual(
            choices_from_group_queryset(Group.objects.none()),
            [],
        )

        # Main groups only
        choices = choices_from_group_queryset(
            Group.objects.filter(pk__in=[g.pk for g in main_groups])
        )
        self.assertEqual(len(choices), 1, "show one optgroup, hide empty ones")
        self.assertEqual(choices[0][0], "Main IETF Entities")
        self.assertEqual(
            [val for val, _ in choices[0][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(main_groups)],
        )

        # Area groups only
        choices = choices_from_group_queryset(
            Group.objects.filter(pk__in=[g.pk for g in areas])
        )
        self.assertEqual(len(choices), 1, "show one optgroup, hide empty ones")
        self.assertEqual(choices[0][0], "IETF Areas")
        self.assertEqual(
            [val for val, _ in choices[0][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(areas)],
        )

        # WGs only
        choices = choices_from_group_queryset(
            Group.objects.filter(pk__in=[g.pk for g in wgs])
        )
        self.assertEqual(len(choices), 1, "show one optgroup, hide empty ones")
        self.assertEqual(choices[0][0], "IETF Working Groups")
        self.assertEqual(
            [val for val, _ in choices[0][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(wgs)],
        )

        # All together
        choices = choices_from_group_queryset(
            Group.objects.filter(pk__in=[g.pk for g in main_groups + areas + wgs])
        )
        self.assertEqual(len(choices), 3, "show all three optgroups")
        self.assertEqual(
            [optgroup_label for optgroup_label, _ in choices],
            ["Main IETF Entities", "IETF Areas", "IETF Working Groups"],
        )
        self.assertEqual(
            [val for val, _ in choices[0][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(main_groups)],
        )
        self.assertEqual(
            [val for val, _ in choices[1][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(areas)],
        )
        self.assertEqual(
            [val for val, _ in choices[2][1]],  # extract the choice value
            [g.pk for g in self._alphabetically_by_acronym(wgs)],
        )

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
