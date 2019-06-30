# Copyright The IETF Trust 2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.utils.test_utils import TestCase
from .mailarch import hash_list_message_id

class HashTest(TestCase):

    def test_hash_list_message_id(self):
        for list, msgid, hash in (
                ('ietf', '156182196167.12901.11966487185176024571@ietfa.amsl.com',  b'lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                ('codesprints', 'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',       b'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                ('xml2rfc', '3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org',  b'g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (u'ietf', u'156182196167.12901.11966487185176024571@ietfa.amsl.com',b'lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (u'codesprints', u'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     b'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (u'xml2rfc', u'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org',b'g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (b'ietf', b'156182196167.12901.11966487185176024571@ietfa.amsl.com',b'lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (b'codesprints', b'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     b'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (b'xml2rfc', b'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org',b'g6DN4SxJGDrlSuKsubwb6rRSePU'),
            ):
            self.assertEqual(hash, hash_list_message_id(list, msgid))
            
