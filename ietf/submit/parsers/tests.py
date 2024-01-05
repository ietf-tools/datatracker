# Copyright The IETF Trust 2023, All Rights Reserved


from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

from ietf.utils.test_utils import TestCase

from .base import FileParser


@override_settings(IDSUBMIT_MAX_DRAFT_SIZE={"txt": 100})
class FileParserTests(TestCase):
    class MyParser(FileParser):
        """Test parser class (FileParser is not usable on its own)"""

        ext = "txt"

    def test_invalid_encoding(self):
        fp = self.MyParser(
            SimpleUploadedFile(
                name="valid-name.txt",
                content=b"This is not valid utf-8 -> \xfe",
                content_type="text/plain",
            )
        )
        parse_info = fp.critical_parse()
        self.assertEqual(len(parse_info.errors), 1)
        self.assertIn("Invalid utf-8 byte(s)", parse_info.errors[0])
        self.assertIn("0xfe", parse_info.errors[0])

    def test_file_too_big(self):
        fp = self.MyParser(
            SimpleUploadedFile(
                name="valid-name.txt",
                content=b"1" + b"ten chars!" * 10,  # exceeds max size of 100
                content_type="text/plain",
            )
        )
        parse_info = fp.critical_parse()
        self.assertEqual(len(parse_info.errors), 1)
        self.assertIn("File size is larger", parse_info.errors[0])

    def test_wrong_extension(self):
        fp = self.MyParser(
            SimpleUploadedFile(
                name="invalid-ext.xml",
                content=b"This is fine",
                content_type="text/plain",
            )
        )
        parse_info = fp.critical_parse()
        self.assertEqual(len(parse_info.errors), 1)
        self.assertIn("Expected the TXT file to have extension", parse_info.errors[0])

    def test_invalid_char_in_filename(self):
        # Can't test "/" in the filename because SimpleUploadedFile treats it as a path separator
        for invalid_char in r"&\;*$ ":
            uploaded_file = SimpleUploadedFile(
                name="invalid" + invalid_char + "name.txt",
                content=b"This is fine",
                content_type="text/plain",
            )
            fp = self.MyParser(uploaded_file)
            parse_info = fp.critical_parse()
            self.assertEqual(
                len(parse_info.errors), 1, f"{invalid_char} should trigger 1 error"
            )
            self.assertIn(
                "Invalid characters were found",
                parse_info.errors[0],
                f"{invalid_char} is an invalid char",
            )
            self.assertIn(
                f": {invalid_char}",
                parse_info.errors[0],
                f"{invalid_char} is the invalid char",
            )
