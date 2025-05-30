# Copyright The IETF Trust 2025, All Rights Reserved
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group
from ietf.liaisons.forms import (
    flatten_choices,
    choices_from_group_queryset,
    all_internal_groups,
    internal_groups_for_person,
    external_groups_for_person,
)
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
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
        # test relies on the data created in ietf.utils.test_data.make_immutable_test_data()
        self.assertCountEqual(
            all_internal_groups().values_list("acronym", flat=True),
            {"ietf", "iab", "iesg", "farfut", "ops", "sops"},
        )

    def test_internal_groups_for_person(self):
        # test relies on the data created in ietf.utils.test_data.make_immutable_test_data()
        # todo add liaison coordinator when modeled
        RoleFactory(
            name_id="execdir",
            group=Group.objects.get(acronym="iab"),
            person__user__username="iab-execdir",
        )
        RoleFactory(
            name_id="auth",
            group__type_id="sdo",
            group__acronym="sdo",
            person__user__username="sdo-authperson",
        )

        self.assertQuerysetEqual(
            internal_groups_for_person(None),
            Group.objects.none(),
            msg="no Person means no groups",
        )
        self.assertQuerysetEqual(
            internal_groups_for_person(PersonFactory()),
            Group.objects.none(),
            msg="no Role means no groups",
        )

        for username in (
            "secretary",
            "ietf-chair",
            "iab-chair",
            "iab-execdir",
            "sdo-authperson",
        ):
            returned_queryset = internal_groups_for_person(
                Person.objects.get(user__username=username)
            )
            self.assertCountEqual(
                returned_queryset.values_list("acronym", flat=True),
                {"ietf", "iab", "iesg", "farfut", "ops", "sops"},
                f"{username} should get all groups",
            )

        # "ops-ad" user is the AD of the "ops" area, which contains the "sops" wg
        self.assertCountEqual(
            internal_groups_for_person(
                Person.objects.get(user__username="ops-ad")
            ).values_list("acronym", flat=True),
            {"ietf", "iesg", "ops", "sops"},
            "area director should get only their area, its wgs, and the ietf/iesg groups",
        )

        self.assertCountEqual(
            internal_groups_for_person(
                Person.objects.get(user__username="sopschairman"),
            ).values_list("acronym", flat=True),
            {"sops"},
            "wg chair should get only their wg",
        )

    def test_external_groups_for_person(self):
        RoleFactory(
            name_id="execdir",
            group=Group.objects.get(acronym="iab"),
            person__user__username="iab-execdir",
        )
        RoleFactory(name_id="liaison_coordinator", group__acronym="iab", person__user__username="liaison-coordinator")
        the_sdo = GroupFactory(type_id="sdo", acronym="the-sdo")
        liaison_manager = RoleFactory(name_id="liaiman", group=the_sdo).person
        authperson = RoleFactory(name_id="auth", group=the_sdo).person

        GroupFactory(acronym="other-sdo", type_id="sdo")
        for username in (
            "secretary",
            "ietf-chair",
            "iab-chair",
            "iab-execdir",
            "liaison-coordinator",
            "ad",
            "sopschairman",
            "sopssecretary",
        ):
            person = Person.objects.get(user__username=username)
            self.assertCountEqual(
                external_groups_for_person(
                    person,
                ).values_list("acronym", flat=True),
                {"the-sdo", "other-sdo"},
                f"{username} should get all SDO groups",
            )
            tmp_role = RoleFactory(name_id="chair", group__type_id="wg", person=person)
            self.assertCountEqual(
                external_groups_for_person(
                    person,
                ).values_list("acronym", flat=True),
                {"the-sdo", "other-sdo"},
                f"{username} should still get all SDO groups when they also a liaison manager",
            )
            tmp_role.delete()

        self.assertCountEqual(
            external_groups_for_person(liaison_manager).values_list(
                "acronym", flat=True
            ),
            {"the-sdo"},
            "liaison manager should get only their SDO group",
        )
        self.assertCountEqual(
            external_groups_for_person(authperson).values_list("acronym", flat=True),
            {"the-sdo"},
            "authorized individual should get only their SDO group",
        )

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
