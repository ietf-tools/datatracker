# Copyright The IETF Trust 2025-2026, All Rights Reserved
import datetime
from hashlib import sha384

from django.core.files.base import ContentFile

from ietf.utils.test_utils import TestCase
from .factories import BlobFactory
from .models import Blob
from .storage import BlobFile, BlobdbStorage


class StorageTests(TestCase):
    def test_save(self):
        storage = BlobdbStorage(bucket_name="my-bucket")
        timestamp = datetime.datetime(
            2025,
            3,
            17,
            1,
            2,
            3,
            tzinfo=datetime.timezone.utc,
        )
        # Create file to save
        my_file = BlobFile(
            content=b"These are my bytes.",
            mtime=timestamp,
            content_type="application/x-my-content-type",
        )
        # save the file
        saved_name = storage.save("myfile.txt", my_file)
        # validate the outcome
        self.assertEqual(saved_name, "myfile.txt")
        blob = Blob.objects.filter(bucket="my-bucket", name="myfile.txt").first()
        self.assertIsNotNone(blob)  # validates bucket and name
        self.assertEqual(bytes(blob.content), b"These are my bytes.")
        self.assertEqual(blob.mtime, timestamp)
        self.assertEqual(blob.content_type, "application/x-my-content-type")

    def test_save_naive_file(self):
        storage = BlobdbStorage(bucket_name="my-bucket")
        my_naive_file = ContentFile(content=b"These are my naive bytes.")
        # save the file
        saved_name = storage.save("myfile.txt", my_naive_file)
        # validate the outcome
        self.assertEqual(saved_name, "myfile.txt")
        blob = Blob.objects.filter(bucket="my-bucket", name="myfile.txt").first()
        self.assertIsNotNone(blob)  # validates bucket and name
        self.assertEqual(bytes(blob.content), b"These are my naive bytes.")
        self.assertIsNone(blob.mtime)
        self.assertEqual(blob.content_type, "")

    def test_open(self):
        """BlobdbStorage open yields a BlobFile with specific mtime and content_type"""
        mtime = datetime.datetime(2021, 1, 2, 3, 45, tzinfo=datetime.timezone.utc)
        blob = BlobFactory(mtime=mtime, content_type="application/x-oh-no-you-didnt")
        storage = BlobdbStorage(bucket_name=blob.bucket)
        with storage.open(blob.name, "rb") as f:
            self.assertTrue(isinstance(f, BlobFile))
            assert isinstance(f, BlobFile)  # redundant, narrows type for linter
            self.assertEqual(f.read(), bytes(blob.content))
            self.assertEqual(f.mtime, mtime)
            self.assertEqual(f.content_type, "application/x-oh-no-you-didnt")

    def test_open_null_mtime(self):
        """BlobdbStorage open yields a BlobFile with default mtime and content_type"""
        blob = BlobFactory(
            content_type="application/x-oh-no-you-didnt"
        )  # does not set mtime
        storage = BlobdbStorage(bucket_name=blob.bucket)
        with storage.open(blob.name, "rb") as f:
            self.assertTrue(isinstance(f, BlobFile))
            assert isinstance(f, BlobFile)  # redundant, narrows type for linter
            self.assertEqual(f.read(), bytes(blob.content))
            self.assertIsNotNone(f.mtime)
            self.assertEqual(f.mtime, blob.modified)
            self.assertEqual(f.content_type, "application/x-oh-no-you-didnt")

    def test_open_file_not_found(self):
        storage = BlobdbStorage(bucket_name="not-a-bucket")
        with self.assertRaises(FileNotFoundError):
            storage.open("definitely/not-a-file.txt")


class BlobModelTests(TestCase):
    @staticmethod
    def _digest(content: bytes) -> str:
        return sha384(content, usedforsecurity=False).hexdigest()

    def test_save_sets_checksum(self):
        blob = BlobFactory(content=b"original")
        stored = Blob.objects.get(pk=blob.pk)
        self.assertEqual(stored.checksum, self._digest(b"original"))

        blob.content = b"replaced"
        blob.content_type = "text/plain"
        blob.save()
        stored = Blob.objects.get(pk=blob.pk)
        self.assertEqual(bytes(stored.content), b"replaced")
        self.assertEqual(stored.checksum, self._digest(b"replaced"))
        self.assertEqual(stored.content_type, "text/plain")

    def test_partial_save_with_content_updates_checksum(self):
        blob = BlobFactory(content=b"original")
        blob.content = b"replaced"
        blob.save(update_fields=["content"])
        stored = Blob.objects.get(pk=blob.pk)
        self.assertEqual(bytes(stored.content), b"replaced")
        self.assertEqual(stored.checksum, self._digest(b"replaced"))

    def test_partial_save_without_content_leaves_checksum(self):
        blob = BlobFactory(content=b"original", content_type="text/plain")
        blob.content = b"not saved"
        blob.content_type = "application/octet-stream"
        blob.save(update_fields=["content_type"])
        stored = Blob.objects.get(pk=blob.pk)
        self.assertEqual(stored.content_type, "application/octet-stream")
        self.assertEqual(bytes(stored.content), b"original")
        self.assertEqual(stored.checksum, self._digest(b"original"))
