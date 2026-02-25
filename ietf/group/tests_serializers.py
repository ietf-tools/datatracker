# Copyright The IETF Trust 2026, All Rights Reserved
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.group.serializers import (
    AreaDirectorSerializer,
    AreaSerializer,
    GroupSerializer,
)
from ietf.person.factories import EmailFactory
from ietf.utils.test_utils import TestCase


class GroupSerializerTests(TestCase):
    def test_serializes(self):
        wg = GroupFactory()
        serialized = GroupSerializer(wg).data
        self.assertEqual(
            serialized,
            {
                "acronym": wg.acronym,
                "name": wg.name,
                "type": "wg",
                "list_email": wg.list_email,
            },
        )


class AreaDirectorSerializerTests(TestCase):
    def test_serializes_role(self):
        """Should serialize a Role correctly"""
        role = RoleFactory(group__type_id="area", name_id="ad")
        serialized = AreaDirectorSerializer(role).data
        self.assertEqual(
            serialized,
            {"email": role.email.email_address()},
        )

    def test_serializes_email(self):
        """Should serialize an Email correctly"""
        email = EmailFactory()
        serialized = AreaDirectorSerializer(email).data
        self.assertEqual(
            serialized,
            {"email": email.email_address()},
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
                "type": area.type.slug,
                "ads": [],
            },
        )
        ad_roles = RoleFactory.create_batch(2, group=area, name_id="ad")
        serialized = AreaSerializer(area).data
        self.assertEqual(serialized["acronym"], area.acronym)
        self.assertEqual(serialized["name"], area.name)
        self.assertEqual(serialized["type"], area.type.slug)
        self.assertCountEqual(
            serialized["ads"],
            [{"email": ad.email.email_address()} for ad in ad_roles],
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
                "type": area.type.slug,
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
                "type": area.type.slug,
                "ads": [],
            },
        )
