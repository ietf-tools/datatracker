# Copyright The IETF Trust 2026, All Rights Reserved

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import override_settings
from ietf import settings
from ietf.doc.storage_utils import exists_in_storage, retrieve_str
from ietf.sync.utils import build_from_file_content, load_rfcs_into_blobdb, rsync_helper
from ietf.utils.test_utils import TestCase


class RsyncHelperTests(TestCase):
    def test_rsync_helper(self):
        with (
            TemporaryDirectory() as source_dir,
            TemporaryDirectory() as dest_dir,
        ):
            with (Path(source_dir) / "canary.txt").open("w") as canary_source_file:
                canary_source_file.write("chirp")
            rsync_helper(
                [
                    "-a",
                    f"{source_dir}/",
                    f"{dest_dir}/",
                ]
            )
            with (Path(dest_dir) / "canary.txt").open("r") as canary_dest_file:
                chirp = canary_dest_file.read()
            self.assertEqual(chirp, "chirp")

    def test_build_from_file_content(self):
        content = build_from_file_content([12345, 54321])
        self.assertEqual(
            content,
            """prerelease/
rfc12345.txt
rfc12345.html
rfc12345.xml
rfc12345.pdf
rfc12345.ps
rfc12345.json
prerelease/rfc12345.notprepped.xml
rfc54321.txt
rfc54321.html
rfc54321.xml
rfc54321.pdf
rfc54321.ps
rfc54321.json
prerelease/rfc54321.notprepped.xml
""",
        )


class RfcBlobUploadTests(TestCase):
    def test_load_rfcs_into_blobdb(self):
        with TemporaryDirectory() as faux_rfc_path:
            with override_settings(RFC_PATH=faux_rfc_path):
                rfc_path = Path(faux_rfc_path)
                (rfc_path / "prerelease").mkdir()
                for num in [12345, 54321]:
                    for ext in settings.RFC_FILE_TYPES + ("json",):
                        with (rfc_path / f"rfc{num}.{ext}").open("w") as f:
                            f.write(ext)
                    with (rfc_path / "rfc{num}.bogon").open("w") as f:
                        f.write("bogon")
                    with (rfc_path / "prerelease" / f"rfc{num}.notprepped.xml").open(
                        "w"
                    ) as f:
                        f.write("notprepped")
                load_rfcs_into_blobdb([12345, 54321])
                for num in [12345, 54321]:
                    for ext in settings.RFC_FILE_TYPES + ("json",):
                        self.assertEqual(
                            retrieve_str("rfc", f"{ext}/rfc{num}.{ext}"),
                            ext,
                        )
                    self.assertFalse(exists_in_storage("rfc", f"bogon/rfc{num}.bogon"))
                    self.assertEqual(
                        retrieve_str("rfc", f"notprepped/rfc{num}.notprepped.xml"),
                        "notprepped",
                    )
