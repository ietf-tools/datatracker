# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-
from ietf.doc.factories import DocAliasFactory
from ietf.utils.test_utils import TestCase

from .factories import RfcToBeFactory, UnusableRfcNumberFactory
from .utils import next_rfc_number


class UtilsTests(TestCase):
    def test_next_rfc_number(self):
        self.assertEqual(next_rfc_number(), [1])
        self.assertEqual(next_rfc_number(2), [1, 2])
        self.assertEqual(next_rfc_number(5), [1, 2, 3, 4, 5])

        UnusableRfcNumberFactory(number=1)
        self.assertEqual(next_rfc_number(), [2])
        self.assertEqual(next_rfc_number(2), [2, 3])
        self.assertEqual(next_rfc_number(5), [2, 3, 4, 5, 6])

        RfcToBeFactory(rfc_number=2)
        self.assertEqual(next_rfc_number(), [3])
        self.assertEqual(next_rfc_number(2), [3, 4])
        self.assertEqual(next_rfc_number(5), [3, 4, 5, 6, 7])

        DocAliasFactory(name="rfc3")
        self.assertEqual(next_rfc_number(), [4])
        self.assertEqual(next_rfc_number(2), [4, 5])
        self.assertEqual(next_rfc_number(5), [4, 5, 6, 7, 8])

        # next_rfc_number is not done until this one passes!
        # UnusableRfcNumberFactory(number=6)
        # self.assertEqual(next_rfc_number(), [4])
        # self.assertEqual(next_rfc_number(2), [4, 5])
        # self.assertEqual(next_rfc_number(5), [7, 8, 9, 10, 11])
