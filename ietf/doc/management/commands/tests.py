# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

from io import StringIO

from django.core.management import call_command, CommandError

from ietf.doc.factories import DocumentAuthorFactory, WgDraftFactory, WgRfcFactory
from ietf.doc.models import Document, DocumentAuthor
from ietf.utils.test_utils import TestCase


class CommandTests(TestCase):
    @staticmethod
    def _call_command(command_name, *args, **options):
        """Call command, capturing (and suppressing) output"""
        out = StringIO()
        err = StringIO()
        options["stdout"] = out
        options["stderr"] = err
        call_command(command_name, *args, **options)
        return out.getvalue(), err.getvalue()

    def test_reset_rfc_authors(self):
        command_name = "reset_rfc_authors"

        draft = WgDraftFactory()
        DocumentAuthorFactory.create_batch(3, document=draft)
        rfc = WgRfcFactory()  # rfc does not yet have a draft
        DocumentAuthorFactory.create_batch(3, document=rfc)
        bad_rfc_num = (
            1
            + Document.objects.filter(rfc_number__isnull=False)
            .order_by("-rfc_number")
            .first()
            .rfc_number
        )
        docauthor_fields = [
            field.name
            for field in DocumentAuthor._meta.get_fields()
            if field.name not in ["document", "id"]
        ]

        with self.assertRaises(CommandError, msg="Cannot reset a bad RFC number"):
            self._call_command(command_name, bad_rfc_num)

        with self.assertRaises(CommandError, msg="Cannot reset an RFC with no draft"):
            self._call_command(command_name, rfc.rfc_number)

        with self.assertRaises(CommandError, msg="Cannot force-reset an RFC with no draft"):
            self._call_command(command_name, rfc.rfc_number, "--force")

        # Link the draft to the rfc
        rfc.targets_related.create(relationship_id="became_rfc", source=draft)

        with self.assertRaises(CommandError, msg="Cannot reset an RFC with authors"):
            self._call_command(command_name, rfc.rfc_number)

        # Calling with force should work
        self._call_command(command_name, rfc.rfc_number, "--force")
        self.assertCountEqual(
            draft.documentauthor_set.values(*docauthor_fields),
            rfc.documentauthor_set.values(*docauthor_fields),
        )

        # Calling on an RFC with no authors should also work
        rfc.documentauthor_set.all().delete()
        self._call_command(command_name, rfc.rfc_number)
        self.assertCountEqual(
            draft.documentauthor_set.values(*docauthor_fields),
            rfc.documentauthor_set.values(*docauthor_fields),
        )
