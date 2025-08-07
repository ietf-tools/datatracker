"""
Type annotations for s3 service client paginators.

[Documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/)

Usage::

    ```python
    from boto3.session import Session

    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_s3.paginator import (
        ListBucketsPaginator,
        ListDirectoryBucketsPaginator,
        ListMultipartUploadsPaginator,
        ListObjectVersionsPaginator,
        ListObjectsPaginator,
        ListObjectsV2Paginator,
        ListPartsPaginator,
    )

    session = Session()
    client: S3Client = session.client("s3")

    list_buckets_paginator: ListBucketsPaginator = client.get_paginator("list_buckets")
    list_directory_buckets_paginator: ListDirectoryBucketsPaginator = client.get_paginator("list_directory_buckets")
    list_multipart_uploads_paginator: ListMultipartUploadsPaginator = client.get_paginator("list_multipart_uploads")
    list_object_versions_paginator: ListObjectVersionsPaginator = client.get_paginator("list_object_versions")
    list_objects_paginator: ListObjectsPaginator = client.get_paginator("list_objects")
    list_objects_v2_paginator: ListObjectsV2Paginator = client.get_paginator("list_objects_v2")
    list_parts_paginator: ListPartsPaginator = client.get_paginator("list_parts")
    ```

Copyright 2025 Vlad Emelianov
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from botocore.paginate import PageIterator, Paginator

from .type_defs import (
    ListBucketsOutputTypeDef,
    ListBucketsRequestPaginateTypeDef,
    ListDirectoryBucketsOutputTypeDef,
    ListDirectoryBucketsRequestPaginateTypeDef,
    ListMultipartUploadsOutputTypeDef,
    ListMultipartUploadsRequestPaginateTypeDef,
    ListObjectsOutputTypeDef,
    ListObjectsRequestPaginateTypeDef,
    ListObjectsV2OutputTypeDef,
    ListObjectsV2RequestPaginateTypeDef,
    ListObjectVersionsOutputTypeDef,
    ListObjectVersionsRequestPaginateTypeDef,
    ListPartsOutputTypeDef,
    ListPartsRequestPaginateTypeDef,
)

if sys.version_info >= (3, 12):
    from typing import Unpack
else:
    from typing_extensions import Unpack

__all__ = (
    "ListBucketsPaginator",
    "ListDirectoryBucketsPaginator",
    "ListMultipartUploadsPaginator",
    "ListObjectVersionsPaginator",
    "ListObjectsPaginator",
    "ListObjectsV2Paginator",
    "ListPartsPaginator",
)

if TYPE_CHECKING:
    _ListBucketsPaginatorBase = Paginator[ListBucketsOutputTypeDef]
else:
    _ListBucketsPaginatorBase = Paginator  # type: ignore[assignment]

class ListBucketsPaginator(_ListBucketsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListBuckets.html#S3.Paginator.ListBuckets)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listbucketspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListBucketsRequestPaginateTypeDef]
    ) -> PageIterator[ListBucketsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListBuckets.html#S3.Paginator.ListBuckets.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listbucketspaginator)
        """

if TYPE_CHECKING:
    _ListDirectoryBucketsPaginatorBase = Paginator[ListDirectoryBucketsOutputTypeDef]
else:
    _ListDirectoryBucketsPaginatorBase = Paginator  # type: ignore[assignment]

class ListDirectoryBucketsPaginator(_ListDirectoryBucketsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListDirectoryBuckets.html#S3.Paginator.ListDirectoryBuckets)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listdirectorybucketspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListDirectoryBucketsRequestPaginateTypeDef]
    ) -> PageIterator[ListDirectoryBucketsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListDirectoryBuckets.html#S3.Paginator.ListDirectoryBuckets.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listdirectorybucketspaginator)
        """

if TYPE_CHECKING:
    _ListMultipartUploadsPaginatorBase = Paginator[ListMultipartUploadsOutputTypeDef]
else:
    _ListMultipartUploadsPaginatorBase = Paginator  # type: ignore[assignment]

class ListMultipartUploadsPaginator(_ListMultipartUploadsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListMultipartUploads.html#S3.Paginator.ListMultipartUploads)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listmultipartuploadspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListMultipartUploadsRequestPaginateTypeDef]
    ) -> PageIterator[ListMultipartUploadsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListMultipartUploads.html#S3.Paginator.ListMultipartUploads.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listmultipartuploadspaginator)
        """

if TYPE_CHECKING:
    _ListObjectVersionsPaginatorBase = Paginator[ListObjectVersionsOutputTypeDef]
else:
    _ListObjectVersionsPaginatorBase = Paginator  # type: ignore[assignment]

class ListObjectVersionsPaginator(_ListObjectVersionsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectVersions.html#S3.Paginator.ListObjectVersions)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectversionspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListObjectVersionsRequestPaginateTypeDef]
    ) -> PageIterator[ListObjectVersionsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectVersions.html#S3.Paginator.ListObjectVersions.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectversionspaginator)
        """

if TYPE_CHECKING:
    _ListObjectsPaginatorBase = Paginator[ListObjectsOutputTypeDef]
else:
    _ListObjectsPaginatorBase = Paginator  # type: ignore[assignment]

class ListObjectsPaginator(_ListObjectsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjects.html#S3.Paginator.ListObjects)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListObjectsRequestPaginateTypeDef]
    ) -> PageIterator[ListObjectsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjects.html#S3.Paginator.ListObjects.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectspaginator)
        """

if TYPE_CHECKING:
    _ListObjectsV2PaginatorBase = Paginator[ListObjectsV2OutputTypeDef]
else:
    _ListObjectsV2PaginatorBase = Paginator  # type: ignore[assignment]

class ListObjectsV2Paginator(_ListObjectsV2PaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectsV2.html#S3.Paginator.ListObjectsV2)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectsv2paginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListObjectsV2RequestPaginateTypeDef]
    ) -> PageIterator[ListObjectsV2OutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectsV2.html#S3.Paginator.ListObjectsV2.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listobjectsv2paginator)
        """

if TYPE_CHECKING:
    _ListPartsPaginatorBase = Paginator[ListPartsOutputTypeDef]
else:
    _ListPartsPaginatorBase = Paginator  # type: ignore[assignment]

class ListPartsPaginator(_ListPartsPaginatorBase):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListParts.html#S3.Paginator.ListParts)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listpartspaginator)
    """
    def paginate(  # type: ignore[override]
        self, **kwargs: Unpack[ListPartsRequestPaginateTypeDef]
    ) -> PageIterator[ListPartsOutputTypeDef]:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListParts.html#S3.Paginator.ListParts.paginate)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/paginators/#listpartspaginator)
        """
