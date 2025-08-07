"""
Type annotations for s3 service client waiters.

[Documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/)

Usage::

    ```python
    from boto3.session import Session

    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_s3.waiter import (
        BucketExistsWaiter,
        BucketNotExistsWaiter,
        ObjectExistsWaiter,
        ObjectNotExistsWaiter,
    )

    session = Session()
    client: S3Client = session.client("s3")

    bucket_exists_waiter: BucketExistsWaiter = client.get_waiter("bucket_exists")
    bucket_not_exists_waiter: BucketNotExistsWaiter = client.get_waiter("bucket_not_exists")
    object_exists_waiter: ObjectExistsWaiter = client.get_waiter("object_exists")
    object_not_exists_waiter: ObjectNotExistsWaiter = client.get_waiter("object_not_exists")
    ```

Copyright 2025 Vlad Emelianov
"""

from __future__ import annotations

import sys

from botocore.waiter import Waiter

from .type_defs import HeadBucketRequestWaitTypeDef, HeadObjectRequestWaitTypeDef

if sys.version_info >= (3, 12):
    from typing import Unpack
else:
    from typing_extensions import Unpack

__all__ = (
    "BucketExistsWaiter",
    "BucketNotExistsWaiter",
    "ObjectExistsWaiter",
    "ObjectNotExistsWaiter",
)

class BucketExistsWaiter(Waiter):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/BucketExists.html#S3.Waiter.BucketExists)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#bucketexistswaiter)
    """
    def wait(  # type: ignore[override]
        self, **kwargs: Unpack[HeadBucketRequestWaitTypeDef]
    ) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/BucketExists.html#S3.Waiter.BucketExists.wait)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#bucketexistswaiter)
        """

class BucketNotExistsWaiter(Waiter):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/BucketNotExists.html#S3.Waiter.BucketNotExists)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#bucketnotexistswaiter)
    """
    def wait(  # type: ignore[override]
        self, **kwargs: Unpack[HeadBucketRequestWaitTypeDef]
    ) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/BucketNotExists.html#S3.Waiter.BucketNotExists.wait)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#bucketnotexistswaiter)
        """

class ObjectExistsWaiter(Waiter):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/ObjectExists.html#S3.Waiter.ObjectExists)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#objectexistswaiter)
    """
    def wait(  # type: ignore[override]
        self, **kwargs: Unpack[HeadObjectRequestWaitTypeDef]
    ) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/ObjectExists.html#S3.Waiter.ObjectExists.wait)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#objectexistswaiter)
        """

class ObjectNotExistsWaiter(Waiter):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/ObjectNotExists.html#S3.Waiter.ObjectNotExists)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#objectnotexistswaiter)
    """
    def wait(  # type: ignore[override]
        self, **kwargs: Unpack[HeadObjectRequestWaitTypeDef]
    ) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/waiter/ObjectNotExists.html#S3.Waiter.ObjectNotExists.wait)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/waiters/#objectnotexistswaiter)
        """
