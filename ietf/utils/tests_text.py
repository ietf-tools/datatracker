# Copyright The IETF Trust 2021-2026, All Rights Reserved
from ietf.utils.test_utils import TestCase
from ietf.utils.text import parse_unicode, decode_document_content


class TestDecoders(TestCase):
    def test_parse_unicode(self):
        names = (
            ("=?utf-8?b?4Yuz4YuK4Ym1IOGJoOGJgOGIiA==?=", "ዳዊት በቀለ"),
            ("=?utf-8?b?5Li9IOmDnA==?=", "丽 郜"),
            ("=?utf-8?b?4KSV4KSu4KWN4KSs4KWL4KScIOCkoeCkvuCksA==?=", "कम्बोज डार"),
            ("=?utf-8?b?zpfPgc6szrrOu861zrnOsSDOm865z4zOvc+Ezrc=?=", "Ηράκλεια Λιόντη"),
            ("=?utf-8?b?15nXqdeo15DXnCDXqNeV15bXoNek15zXkw==?=", "ישראל רוזנפלד"),
            ("=?utf-8?b?5Li95Y2OIOeahw==?=", "丽华 皇"),
            ("=?utf-8?b?77ul77qu766V77qzIO+tlu+7ru+vvu+6ju+7pw==?=", "ﻥﺮﮕﺳ ﭖﻮﯾﺎﻧ"),
            (
                "=?utf-8?b?77uh77uu77qz77uu76++IO+6su+7tO+7p++6jSDvurDvu6Pvuo7vu6jvr74=?=",
                "ﻡﻮﺳﻮﯾ ﺲﻴﻧﺍ ﺰﻣﺎﻨﯾ",
            ),
            (
                "=?utf-8?b?ScOxaWdvIFNhbsOnIEliw6HDsWV6IGRlIGxhIFBlw7Fh?=",
                "Iñigo Sanç Ibáñez de la Peña",
            ),
            ("Mart van Oostendorp", "Mart van Oostendorp"),
            ("", ""),
        )
        for encoded_str, unicode in names:
            self.assertEqual(unicode, parse_unicode(encoded_str))

    def test_decode_document_content(self):
        utf8_bytes = "𒀭𒊩𒌆𒄈𒋢".encode("utf-8")  # ends with 4-byte character
        latin1_bytes = "àéîøü".encode("latin-1")
        other_bytes = "àéîøü".encode("macintosh")  # different from its latin-1 encoding
        assert other_bytes.decode("macintosh") != other_bytes.decode("latin-1"),\
            "test broken: other_bytes must decode differently as latin-1"

        # simplest case
        self.assertEqual(
            decode_document_content(utf8_bytes),
            utf8_bytes.decode(),
        )
        # losing 1-4 bytes from the end leave the last character incomplete; the
        # decoder should decode all but that last character
        self.assertEqual(
            decode_document_content(utf8_bytes[:-1]),
            utf8_bytes.decode()[:-1],
        )
        self.assertEqual(
            decode_document_content(utf8_bytes[:-2]),
            utf8_bytes.decode()[:-1],
        )
        self.assertEqual(
            decode_document_content(utf8_bytes[:-3]),
            utf8_bytes.decode()[:-1],
        )
        self.assertEqual(
            decode_document_content(utf8_bytes[:-4]),
            utf8_bytes.decode()[:-1],
        )

        # latin-1 is also simple
        self.assertEqual(
            decode_document_content(latin1_bytes),
            latin1_bytes.decode("latin-1"),
        )

        # other character sets are just treated as latin1 (bug? feature? you decide)
        self.assertEqual(
            decode_document_content(other_bytes),
            other_bytes.decode("latin-1"),
        )
