# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import os
import shutil

import debug    # pyflakes:ignore

from celery import shared_task
from contextlib import AbstractContextManager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from django.conf import settings

from .index import all_id_txt, all_id2_txt, id_index_txt


class TempFileManager(AbstractContextManager):
    def __init__(self, tmpdir=None) -> None:
        self.cleanup_list: set[Path] = set()
        self.dir = tmpdir

    def make_temp_file(self, content):
        with NamedTemporaryFile(mode="wt", delete=False, dir=self.dir) as tf:
            tf_path = Path(tf.name)
            self.cleanup_list.add(tf_path)
            tf.write(content)
        return tf_path

    def move_into_place(self, src_path: Path, dest_path: Path, hardlink_dirs: List[Path] = []):
        shutil.move(src_path, dest_path)
        dest_path.chmod(0o644)
        self.cleanup_list.remove(src_path)
        for path in hardlink_dirs:
            target = path / dest_path.name
            target.unlink(missing_ok=True)
            os.link(dest_path, target) # until python>=3.10

    def cleanup(self):
        for tf_path in self.cleanup_list:
            tf_path.unlink(missing_ok=True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False  # False: do not suppress the exception


@shared_task
def idindex_update_task():
    """Update I-D indexes"""
    id_path = Path(settings.INTERNET_DRAFT_PATH)
    derived_path = Path(settings.DERIVED_DIR)
    download_path = Path(settings.ALL_ID_DOWNLOAD_DIR)
    ftp_path = Path(settings.FTP_DIR) / "internet-drafts"
    all_archive_path = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR)

    with TempFileManager() as tmp_mgr:
        # Generate copies of new contents
        all_id_content = all_id_txt()
        all_id_tmpfile = tmp_mgr.make_temp_file(all_id_content)
        derived_all_id_tmpfile = tmp_mgr.make_temp_file(all_id_content)
        download_all_id_tmpfile = tmp_mgr.make_temp_file(all_id_content)

        id_index_content = id_index_txt()
        id_index_tmpfile = tmp_mgr.make_temp_file(id_index_content)
        derived_id_index_tmpfile = tmp_mgr.make_temp_file(id_index_content)
        download_id_index_tmpfile = tmp_mgr.make_temp_file(id_index_content)

        id_abstracts_content = id_index_txt(with_abstracts=True)
        id_abstracts_tmpfile = tmp_mgr.make_temp_file(id_abstracts_content)
        derived_id_abstracts_tmpfile = tmp_mgr.make_temp_file(id_abstracts_content)
        download_id_abstracts_tmpfile = tmp_mgr.make_temp_file(id_abstracts_content)

        all_id2_content = all_id2_txt()
        all_id2_tmpfile = tmp_mgr.make_temp_file(all_id2_content)
        derived_all_id2_tmpfile = tmp_mgr.make_temp_file(all_id2_content)

        # Move temp files as-atomically-as-possible into place
        tmp_mgr.move_into_place(all_id_tmpfile, id_path / "all_id.txt", [ftp_path, all_archive_path])
        tmp_mgr.move_into_place(derived_all_id_tmpfile, derived_path / "all_id.txt")
        tmp_mgr.move_into_place(download_all_id_tmpfile, download_path / "id-all.txt")

        tmp_mgr.move_into_place(id_index_tmpfile, id_path / "1id-index.txt", [ftp_path, all_archive_path])
        tmp_mgr.move_into_place(derived_id_index_tmpfile, derived_path / "1id-index.txt")
        tmp_mgr.move_into_place(download_id_index_tmpfile, download_path / "id-index.txt")

        tmp_mgr.move_into_place(id_abstracts_tmpfile, id_path / "1id-abstracts.txt", [ftp_path, all_archive_path])
        tmp_mgr.move_into_place(derived_id_abstracts_tmpfile, derived_path / "1id-abstracts.txt")
        tmp_mgr.move_into_place(download_id_abstracts_tmpfile, download_path / "id-abstract.txt")

        tmp_mgr.move_into_place(all_id2_tmpfile, id_path / "all_id2.txt", [ftp_path, all_archive_path])
        tmp_mgr.move_into_place(derived_all_id2_tmpfile, derived_path / "all_id2.txt")
