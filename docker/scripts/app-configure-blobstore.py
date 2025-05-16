#!/usr/bin/env python
# Copyright The IETF Trust 2024, All Rights Reserved

import boto3
import botocore.config
import botocore.exceptions
import os
import sys

from ietf.settings import ARTIFACT_STORAGE_NAMES


def init_blobstore():
    blobstore = boto3.resource(
        "s3",
        endpoint_url=os.environ.get("BLOB_STORE_ENDPOINT_URL", "http://blobstore:9000"),
        aws_access_key_id=os.environ.get("BLOB_STORE_ACCESS_KEY", "minio_root"),
        aws_secret_access_key=os.environ.get("BLOB_STORE_SECRET_KEY", "minio_pass"),
        aws_session_token=None,
        config=botocore.config.Config(signature_version="s3v4"),
    )
    for bucketname in ARTIFACT_STORAGE_NAMES:
        try:
            blobstore.create_bucket(
                Bucket=f"{os.environ.get('BLOB_STORE_BUCKET_PREFIX', '')}{bucketname}".strip()
            )
        except botocore.exceptions.ClientError as err:
            if err.response["Error"]["Code"] == "BucketAlreadyExists":
                print(f"Bucket {bucketname} already exists")
            else:
                print(f"Error creating {bucketname}: {err.response['Error']['Code']}")
        else:
            print(f"Bucket {bucketname} created")

if __name__ == "__main__":
    sys.exit(init_blobstore())
