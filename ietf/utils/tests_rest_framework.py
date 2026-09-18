# Copyright The IETF Trust 2026, All Rights Reserved
import datetime

from rest_framework import serializers

from ietf.utils.rest_framework.fields import AwareDateTimeField
from ietf.utils.test_utils import TestCase


class AwareDateTimeFieldTests(TestCase):
    class Serializer(serializers.Serializer):
        when = AwareDateTimeField()

    def validated(self, value):
        serializer = self.Serializer(data={"when": value})
        return serializer, serializer.is_valid()

    def test_accepts_utc(self):
        serializer, valid = self.validated("2024-02-21T18:00:00Z")
        self.assertTrue(valid, serializer.errors)
        self.assertEqual(
            serializer.validated_data["when"],
            datetime.datetime(2024, 2, 21, 18, 0, tzinfo=datetime.UTC),
        )

    def test_accepts_other_offsets_as_the_same_instant(self):
        serializer, valid = self.validated("2024-02-21T13:00:00-05:00")
        self.assertTrue(valid, serializer.errors)
        self.assertEqual(
            serializer.validated_data["when"],
            datetime.datetime(2024, 2, 21, 18, 0, tzinfo=datetime.UTC),
        )

    def test_rejects_a_value_with_no_offset(self):
        serializer, valid = self.validated("2024-02-21T18:00:00")
        self.assertFalse(valid, "a naive value must not be accepted")
        self.assertEqual(
            [str(e) for e in serializer.errors["when"]],
            ["Datetime must include a UTC offset."],
        )

    def test_rejects_a_value_that_is_not_a_datetime(self):
        _, valid = self.validated("not a datetime")
        self.assertFalse(valid)
