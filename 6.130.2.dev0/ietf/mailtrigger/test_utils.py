# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from ietf.doc.factories import WgDraftFactory
from ietf.mailtrigger.models import MailTrigger
from .utils import gather_address_lists
from ietf.utils.test_utils import TestCase


class GatherAddressListsTests(TestCase):
    def setUp(self):
        self.doc = WgDraftFactory(group__acronym='mars', rev='01')
        self.author_address = self.doc.name + '@ietf.org'

    def test_regular_trigger(self):
        to, cc = gather_address_lists('doc_pulled_from_rfc_queue', doc=self.doc)
        # Despite its name, assertCountEqual also compares content, but does not care for ordering
        self.assertCountEqual(to, ['iana@iana.org', 'rfc-editor@rfc-editor.org'])
        self.assertCountEqual(cc, ['The IESG <iesg@ietf.org>', self.author_address,
                                        'mars-chairs@ietf.org', 'iesg-secretary@ietf.org'])

    def test_skipped_recipient(self):
        to, cc = gather_address_lists('doc_pulled_from_rfc_queue', doc=self.doc,
                                      skipped_recipients=['mars-chairs@ietf.org', 'iana@iana.org'])
        self.assertCountEqual(to, ['rfc-editor@rfc-editor.org'])
        self.assertCountEqual(cc, ['The IESG <iesg@ietf.org>', self.author_address,
                                        'iesg-secretary@ietf.org'])

    def test_trigger_does_not_exist(self):
        with self.assertRaises(MailTrigger.DoesNotExist):
            gather_address_lists('this-does-not-exist______', doc=self.doc)

    def test_create_if_not_exists(self):
        new_slug = 'doc_pulled_from_rfc_special_autocreated'
        new_desc = 'Autocreated mailtrigger from doc_pulled_from_rfc_queue'
        to, cc = gather_address_lists(new_slug, doc=self.doc, desc_if_not_exists=new_desc,
                                      create_from_slug_if_not_exists='doc_pulled_from_rfc_queue')
        self.assertCountEqual(to, ['iana@iana.org', 'rfc-editor@rfc-editor.org'])
        self.assertCountEqual(cc, ['The IESG <iesg@ietf.org>', self.author_address,
                                        'mars-chairs@ietf.org', 'iesg-secretary@ietf.org'])
        new_trigger = MailTrigger.objects.get(slug=new_slug)
        self.assertEqual(new_trigger.desc, new_desc)
