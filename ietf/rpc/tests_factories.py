# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.rpc.factories import (
    RpcPersonFactory,
    RpcRoleFactory,
)

from ietf.utils.test_utils import TestCase


class RpcPersonFactoryTests(TestCase):
    def test_bare(self):
        p = RpcPersonFactory()
        self.assertFalse(p.can_hold_role.exists())
        self.assertFalse(p.capable_of.exists())

    def test_can_hold_role(self):
        p = RpcPersonFactory(can_hold_role=["foo", "bar"])
        self.assertCountEqual(
            p.can_hold_role.values_list("slug", flat=True), ["foo", "bar"]
        )
        roles = RpcRoleFactory.create_batch(3)
        p = RpcPersonFactory(can_hold_role=roles)
        self.assertCountEqual(p.can_hold_role.all(), roles)
