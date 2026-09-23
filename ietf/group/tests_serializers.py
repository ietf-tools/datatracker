# Copyright The IETF Trust 2026, All Rights Reserved
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.group.serializers import (
    AreaDirectorSerializer,
    AreaSerializer,
    GroupSerializer,
)
from ietf.name.models import GroupStateName
from ietf.person.factories import EmailFactory
from ietf.utils.test_utils import TestCase


class GroupSerializerTests(TestCase):
    def test_serializes(self):
        wg = GroupFactory()
        partial_expected_json = {
            "acronym": wg.acronym,
            "name": wg.name,
            "type": "wg",
            "list_email": wg.list_email,
        }

        self.assertEqual(
            GroupSerializer(wg).data,
            partial_expected_json | {"state": "active"},
        )
        for slug in ["bof-conc", "conclude"]:
            wg.state_id = slug
            wg.save()
            self.assertEqual(
                GroupSerializer(wg).data,
                partial_expected_json | {"state": "concluded"},
            )
        for state in GroupStateName.objects.filter(used=True).exclude(
            slug__in=["active", "bof-conc", "conclude"]
        ):
            wg.state_id = state.slug
            wg.save()
            self.assertEqual(
                GroupSerializer(wg).data,
                partial_expected_json | {"state": "other"},
            )
        # Group.state is nullable, so test that, too
        wg.state = None
        wg.save()
        self.assertEqual(
            GroupSerializer(wg).data,
            partial_expected_json | {"state": "other"},
        )


class AreaDirectorSerializerTests(TestCase):
    def test_serializes_role(self):
        """Should serialize a Role correctly"""
        role = RoleFactory(group__type_id="area", name_id="ad")
        serialized = AreaDirectorSerializer(role).data
        self.assertEqual(
            serialized,
            {"email": role.email.email_address(), "name": role.person.plain_name()},
        )

    def test_serializes_email(self):
        """Should serialize an Email correctly"""
        email = EmailFactory()
        serialized = AreaDirectorSerializer(email).data
        self.assertEqual(
            serialized,
            {
                "email": email.email_address(),
                "name": email.person.plain_name() if email.person else None,
            },
        )


class AreaSerializerTests(TestCase):
    def test_serializes_active_area(self):
        """Should serialize an active area correctly"""
        area = GroupFactory(type_id="area", state_id="active")
        serialized = AreaSerializer(area).data
        self.assertEqual(
            serialized,
            {
                "acronym": area.acronym,
                "name": area.name,
                "ads": [],
            },
        )
        ad_roles = RoleFactory.create_batch(2, group=area, name_id="ad")
        serialized = AreaSerializer(area).data
        self.assertEqual(serialized["acronym"], area.acronym)
        self.assertEqual(serialized["name"], area.name)
        self.assertCountEqual(
            serialized["ads"],
            [
                {"email": ad.email.email_address(), "name": ad.person.plain_name()}
                for ad in ad_roles
            ],
        )

    def test_serializes_inactive_area(self):
        """Should serialize an inactive area correctly"""
        area = GroupFactory(type_id="area", state_id="conclude")
        serialized = AreaSerializer(area).data
        self.assertEqual(
            serialized,
            {
                "acronym": area.acronym,
                "name": area.name,
                "ads": [],
            },
        )
        RoleFactory.create_batch(2, group=area, name_id="ad")
        serialized = AreaSerializer(area).data
        self.assertEqual(
            serialized,
            {
                "acronym": area.acronym,
                "name": area.name,
                "ads": [],
            },
        )
