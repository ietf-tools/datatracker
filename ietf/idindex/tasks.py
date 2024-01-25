# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import shutil

from celery import shared_task
from pathlib import Path
from tempfile import NamedTemporaryFile

from .index import all_id_txt, all_id2_txt, id_index_txt


@shared_task
def idindex_update_task():
    """Update I-D indexes"""
    cleanup_list: set[Path] = set()

    def _make_temp_file(content):
        with NamedTemporaryFile(delete=False, dir="/a/tmp") as tf:
            tf_path = Path(tf.name)
            cleanup_list.add(tf_path)
            tf.write(content)
        return tf_path

    def _move_into_place(src_path: Path, dest_path: Path):
        shutil.move(src_path, dest_path)
        dest_path.chmod(0o644)
        cleanup_list.remove(src_path)

    def _cleanup():
        for tf_path in cleanup_list:
            tf_path.unlink(missing_ok=True)

    id_path = Path("/a/ietfdata/doc/draft/repository")
    derived_path = Path("/a/ietfdata/derived")
    download_path = Path("/a/www/www6s/download")

    # all_id
    try:
        # Generate copies of new contents
        all_id_content = all_id_txt()
        all_id_tmpfile = _make_temp_file(all_id_content)
        derived_all_id_tmpfile = _make_temp_file(all_id_content)
        download_all_id_tmpfile = _make_temp_file(all_id_content)

        id_index_content = id_index_txt()
        id_index_tmpfile = _make_temp_file(id_index_content)
        derived_id_index_tmpfile = _make_temp_file(id_index_content)
        download_id_index_tmpfile = _make_temp_file(id_index_content)

        id_abstracts_content = id_index_txt(with_abstracts=True)
        id_abstracts_tmpfile = _make_temp_file(id_abstracts_content)
        derived_id_abstracts_tmpfile = _make_temp_file(id_abstracts_content)
        download_id_abstracts_tmpfile = _make_temp_file(id_abstracts_content)

        all_id2_content = all_id2_txt()
        all_id2_tmpfile = _make_temp_file(all_id2_content)
        derived_all_id2_tmpfile = _make_temp_file(all_id2_content)

        # Move temp files as-atomically-as-possible into place
        _move_into_place(all_id_tmpfile, id_path / "all_id.txt")
        _move_into_place(derived_all_id_tmpfile, derived_path / "all_id.txt")
        _move_into_place(download_all_id_tmpfile, download_path / "id-all.txt")

        _move_into_place(id_index_tmpfile, id_path / "1id-index.txt")
        _move_into_place(derived_id_index_tmpfile, derived_path / "1id-index.txt")
        _move_into_place(download_id_index_tmpfile, download_path / "id-index.txt")

        _move_into_place(id_abstracts_tmpfile, id_path / "1id-abstracts.txt")
        _move_into_place(derived_id_abstracts_tmpfile, derived_path / "1id-abstracts.txt")
        _move_into_place(download_id_abstracts_tmpfile, download_path / "id-abstract.txt")

        _move_into_place(all_id2_tmpfile, id_path / "all_id2.txt")
        _move_into_place(derived_all_id2_tmpfile, derived_path / "all_id2.txt")
    finally:
        _cleanup()
