# Copyright The IETF Trust 2021-2026, All Rights Reserved
from ietf.utils.test_utils import TestCase
from ietf.utils.text import parse_unicode


class TestRFC2047Strings(TestCase):
    def test_parse_unicode(self):
        names = (
            ('=?utf-8?b?4Yuz4YuK4Ym1IOGJoOGJgOGIiA==?=', 'ዳዊት በቀለ'),
            ('=?utf-8?b?5Li9IOmDnA==?=', '丽 郜'),
            ('=?utf-8?b?4KSV4KSu4KWN4KSs4KWL4KScIOCkoeCkvuCksA==?=', 'कम्बोज डार'),
            ('=?utf-8?b?zpfPgc6szrrOu861zrnOsSDOm865z4zOvc+Ezrc=?=', 'Ηράκλεια Λιόντη'),
            ('=?utf-8?b?15nXqdeo15DXnCDXqNeV15bXoNek15zXkw==?=', 'ישראל רוזנפלד'),
            ('=?utf-8?b?5Li95Y2OIOeahw==?=', '丽华 皇'),
            ('=?utf-8?b?77ul77qu766V77qzIO+tlu+7ru+vvu+6ju+7pw==?=', 'ﻥﺮﮕﺳ ﭖﻮﯾﺎﻧ'),
            ('=?utf-8?b?77uh77uu77qz77uu76++IO+6su+7tO+7p++6jSDvurDvu6Pvuo7vu6jvr74=?=', 'ﻡﻮﺳﻮﯾ ﺲﻴﻧﺍ ﺰﻣﺎﻨﯾ'),
            ('=?utf-8?b?ScOxaWdvIFNhbsOnIEliw6HDsWV6IGRlIGxhIFBlw7Fh?=', 'Iñigo Sanç Ibáñez de la Peña'),
            ('Mart van Oostendorp', 'Mart van Oostendorp'),
            ('', ''),
            )
        for encoded_str, unicode in names: 
            self.assertEqual(unicode, parse_unicode(encoded_str))

