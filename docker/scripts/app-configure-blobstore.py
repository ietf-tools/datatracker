#!/usr/bin/env python
# Copyright The IETF Trust 2024, All Rights Reserved

import boto3
import sys

def init_blobstore():
    blobstore = boto3.resource("s3",
        endpoint_url="http://blobstore:9000",
        aws_access_key_id="minio_root",
        aws_secret_access_key="minio_pass",
        aws_session_token=None,
        config=boto3.session.Config(signature_version="s3v4"),
        verify=False
    )
    for bucketname in [
        "agenda",
        "bluesheets",
        "bofreq",
        "charter",
        "chatlog",
        "conflrev",
        "draft-xml",
        "draft-txt",
        "draft-html",
        "draft-htmlized",
        "draft-pdf",
        "draft-pdfized",
        "liai-att",
        "liaison",
        "minutes",
        "narrativeminutes",
        "polls",
        "procmaterials",
        "recording",
        "review",
        "rfc-txt",
        "rfc-html",
        "rfc-pdf",
        "rfc-htmlized",
        "rfc-pdfized",
        "slides",
        "statchg",
        "statement",
    ]:
        blobstore.create_bucket(Bucket=bucketname)


if __name__ == "__main__":
    sys.exit(init_blobstore())
