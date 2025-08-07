"""
Type annotations for s3 service ServiceResource.

[Documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/)

Usage::

    ```python
    from boto3.session import Session

    from mypy_boto3_s3.service_resource import S3ServiceResource
    import mypy_boto3_s3.service_resource as s3_resources

    session = Session()
    resource: S3ServiceResource = session.resource("s3")

    my_bucket: s3_resources.Bucket = resource.Bucket(...)
    my_bucket_acl: s3_resources.BucketAcl = resource.BucketAcl(...)
    my_bucket_cors: s3_resources.BucketCors = resource.BucketCors(...)
    my_bucket_lifecycle: s3_resources.BucketLifecycle = resource.BucketLifecycle(...)
    my_bucket_lifecycle_configuration: s3_resources.BucketLifecycleConfiguration = resource.BucketLifecycleConfiguration(...)
    my_bucket_logging: s3_resources.BucketLogging = resource.BucketLogging(...)
    my_bucket_notification: s3_resources.BucketNotification = resource.BucketNotification(...)
    my_bucket_policy: s3_resources.BucketPolicy = resource.BucketPolicy(...)
    my_bucket_request_payment: s3_resources.BucketRequestPayment = resource.BucketRequestPayment(...)
    my_bucket_tagging: s3_resources.BucketTagging = resource.BucketTagging(...)
    my_bucket_versioning: s3_resources.BucketVersioning = resource.BucketVersioning(...)
    my_bucket_website: s3_resources.BucketWebsite = resource.BucketWebsite(...)
    my_multipart_upload: s3_resources.MultipartUpload = resource.MultipartUpload(...)
    my_multipart_upload_part: s3_resources.MultipartUploadPart = resource.MultipartUploadPart(...)
    my_object: s3_resources.Object = resource.Object(...)
    my_object_acl: s3_resources.ObjectAcl = resource.ObjectAcl(...)
    my_object_summary: s3_resources.ObjectSummary = resource.ObjectSummary(...)
    my_object_version: s3_resources.ObjectVersion = resource.ObjectVersion(...)
```

Copyright 2025 Vlad Emelianov
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from boto3.resources.base import ResourceMeta, ServiceResource
from boto3.resources.collection import ResourceCollection
from boto3.s3.transfer import TransferConfig
from botocore.client import BaseClient

from .client import S3Client
from .literals import (
    ArchiveStatusType,
    BucketVersioningStatusType,
    ChecksumAlgorithmType,
    MFADeleteStatusType,
    ObjectLockLegalHoldStatusType,
    ObjectLockModeType,
    ObjectStorageClassType,
    PayerType,
    ReplicationStatusType,
    ServerSideEncryptionType,
    StorageClassType,
    TransitionDefaultMinimumObjectSizeType,
)
from .type_defs import (
    AbortMultipartUploadOutputTypeDef,
    AbortMultipartUploadRequestMultipartUploadAbortTypeDef,
    CompleteMultipartUploadRequestMultipartUploadCompleteTypeDef,
    CopyObjectOutputTypeDef,
    CopyObjectRequestObjectCopyFromTypeDef,
    CopyObjectRequestObjectSummaryCopyFromTypeDef,
    CopySourceTypeDef,
    CORSRuleOutputTypeDef,
    CreateBucketOutputTypeDef,
    CreateBucketRequestBucketCreateTypeDef,
    CreateBucketRequestServiceResourceCreateBucketTypeDef,
    CreateMultipartUploadRequestObjectInitiateMultipartUploadTypeDef,
    CreateMultipartUploadRequestObjectSummaryInitiateMultipartUploadTypeDef,
    DeleteBucketCorsRequestBucketCorsDeleteTypeDef,
    DeleteBucketLifecycleRequestBucketLifecycleConfigurationDeleteTypeDef,
    DeleteBucketLifecycleRequestBucketLifecycleDeleteTypeDef,
    DeleteBucketPolicyRequestBucketPolicyDeleteTypeDef,
    DeleteBucketRequestBucketDeleteTypeDef,
    DeleteBucketTaggingRequestBucketTaggingDeleteTypeDef,
    DeleteBucketWebsiteRequestBucketWebsiteDeleteTypeDef,
    DeleteObjectOutputTypeDef,
    DeleteObjectRequestObjectDeleteTypeDef,
    DeleteObjectRequestObjectSummaryDeleteTypeDef,
    DeleteObjectRequestObjectVersionDeleteTypeDef,
    DeleteObjectsOutputTypeDef,
    DeleteObjectsRequestBucketDeleteObjectsTypeDef,
    ErrorDocumentTypeDef,
    FileobjTypeDef,
    GetObjectOutputTypeDef,
    GetObjectRequestObjectGetTypeDef,
    GetObjectRequestObjectSummaryGetTypeDef,
    GetObjectRequestObjectVersionGetTypeDef,
    GrantTypeDef,
    HeadObjectOutputTypeDef,
    HeadObjectRequestObjectVersionHeadTypeDef,
    IndexDocumentTypeDef,
    InitiatorTypeDef,
    LambdaFunctionConfigurationOutputTypeDef,
    LifecycleRuleOutputTypeDef,
    LoggingEnabledOutputTypeDef,
    OwnerTypeDef,
    PutBucketAclRequestBucketAclPutTypeDef,
    PutBucketCorsRequestBucketCorsPutTypeDef,
    PutBucketLifecycleConfigurationOutputTypeDef,
    PutBucketLifecycleConfigurationRequestBucketLifecycleConfigurationPutTypeDef,
    PutBucketLifecycleRequestBucketLifecyclePutTypeDef,
    PutBucketLoggingRequestBucketLoggingPutTypeDef,
    PutBucketNotificationConfigurationRequestBucketNotificationPutTypeDef,
    PutBucketPolicyRequestBucketPolicyPutTypeDef,
    PutBucketRequestPaymentRequestBucketRequestPaymentPutTypeDef,
    PutBucketTaggingRequestBucketTaggingPutTypeDef,
    PutBucketVersioningRequestBucketVersioningEnableTypeDef,
    PutBucketVersioningRequestBucketVersioningPutTypeDef,
    PutBucketVersioningRequestBucketVersioningSuspendTypeDef,
    PutBucketWebsiteRequestBucketWebsitePutTypeDef,
    PutObjectAclOutputTypeDef,
    PutObjectAclRequestObjectAclPutTypeDef,
    PutObjectOutputTypeDef,
    PutObjectRequestBucketPutObjectTypeDef,
    PutObjectRequestObjectPutTypeDef,
    PutObjectRequestObjectSummaryPutTypeDef,
    QueueConfigurationOutputTypeDef,
    RedirectAllRequestsToTypeDef,
    RestoreObjectOutputTypeDef,
    RestoreObjectRequestObjectRestoreObjectTypeDef,
    RestoreObjectRequestObjectSummaryRestoreObjectTypeDef,
    RestoreStatusTypeDef,
    RoutingRuleTypeDef,
    RuleOutputTypeDef,
    TagTypeDef,
    TopicConfigurationOutputTypeDef,
    UploadPartCopyOutputTypeDef,
    UploadPartCopyRequestMultipartUploadPartCopyFromTypeDef,
    UploadPartOutputTypeDef,
    UploadPartRequestMultipartUploadPartUploadTypeDef,
)

if sys.version_info >= (3, 9):
    from builtins import dict as Dict
    from builtins import list as List
    from collections.abc import Callable, Iterator, Sequence
else:
    from typing import Callable, Dict, Iterator, List, Sequence
if sys.version_info >= (3, 12):
    from typing import Literal, Unpack
else:
    from typing_extensions import Literal, Unpack

__all__ = (
    "Bucket",
    "BucketAcl",
    "BucketCors",
    "BucketLifecycle",
    "BucketLifecycleConfiguration",
    "BucketLogging",
    "BucketMultipartUploadsCollection",
    "BucketNotification",
    "BucketObjectVersionsCollection",
    "BucketObjectsCollection",
    "BucketPolicy",
    "BucketRequestPayment",
    "BucketTagging",
    "BucketVersioning",
    "BucketWebsite",
    "MultipartUpload",
    "MultipartUploadPart",
    "MultipartUploadPartsCollection",
    "Object",
    "ObjectAcl",
    "ObjectSummary",
    "ObjectVersion",
    "S3ServiceResource",
    "ServiceResourceBucketsCollection",
)

class ServiceResourceBucketsCollection(ResourceCollection):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#S3.ServiceResource.buckets)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
    """
    def all(self) -> ServiceResourceBucketsCollection:
        """
        Get all items from the collection, optionally with a custom page size and item
        count limit.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#S3.ServiceResource.all)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

    def filter(  # type: ignore[override]
        self,
        *,
        MaxBuckets: int = ...,
        ContinuationToken: str = ...,
        Prefix: str = ...,
        BucketRegion: str = ...,
    ) -> ServiceResourceBucketsCollection:
        """
        Get items from the collection, passing keyword arguments along as parameters to
        the underlying service operation, which are typically used to filter the
        results.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#filter)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

    def limit(self, count: int) -> ServiceResourceBucketsCollection:
        """
        Return at most this many Buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#limit)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

    def page_size(self, count: int) -> ServiceResourceBucketsCollection:
        """
        Fetch at most this many Buckets per service request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#page_size)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

    def pages(self) -> Iterator[List[Bucket]]:
        """
        A generator which yields pages of Buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#pages)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

    def __iter__(self) -> Iterator[Bucket]:
        """
        A generator which yields Buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/buckets.html#__iter__)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#serviceresourcebucketscollection)
        """

class BucketMultipartUploadsCollection(ResourceCollection):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#S3.Bucket.multipart_uploads)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
    """
    def all(self) -> BucketMultipartUploadsCollection:
        """
        Get all items from the collection, optionally with a custom page size and item
        count limit.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#S3.Bucket.all)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

    def filter(  # type: ignore[override]
        self,
        *,
        Delimiter: str = ...,
        EncodingType: Literal["url"] = ...,
        KeyMarker: str = ...,
        MaxUploads: int = ...,
        Prefix: str = ...,
        UploadIdMarker: str = ...,
        ExpectedBucketOwner: str = ...,
        RequestPayer: Literal["requester"] = ...,
    ) -> BucketMultipartUploadsCollection:
        """
        Get items from the collection, passing keyword arguments along as parameters to
        the underlying service operation, which are typically used to filter the
        results.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#filter)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

    def limit(self, count: int) -> BucketMultipartUploadsCollection:
        """
        Return at most this many MultipartUploads.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#limit)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

    def page_size(self, count: int) -> BucketMultipartUploadsCollection:
        """
        Fetch at most this many MultipartUploads per service request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#page_size)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

    def pages(self) -> Iterator[List[MultipartUpload]]:
        """
        A generator which yields pages of MultipartUploads.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#pages)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

    def __iter__(self) -> Iterator[MultipartUpload]:
        """
        A generator which yields MultipartUploads.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/multipart_uploads.html#__iter__)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketmultipart_uploads)
        """

class BucketObjectVersionsCollection(ResourceCollection):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#S3.Bucket.object_versions)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
    """
    def all(self) -> BucketObjectVersionsCollection:
        """
        Get all items from the collection, optionally with a custom page size and item
        count limit.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#S3.Bucket.all)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def filter(  # type: ignore[override]
        self,
        *,
        Delimiter: str = ...,
        EncodingType: Literal["url"] = ...,
        KeyMarker: str = ...,
        MaxKeys: int = ...,
        Prefix: str = ...,
        VersionIdMarker: str = ...,
        ExpectedBucketOwner: str = ...,
        RequestPayer: Literal["requester"] = ...,
        OptionalObjectAttributes: Sequence[Literal["RestoreStatus"]] = ...,
    ) -> BucketObjectVersionsCollection:
        """
        Get items from the collection, passing keyword arguments along as parameters to
        the underlying service operation, which are typically used to filter the
        results.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#filter)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def delete(
        self,
        *,
        MFA: str = ...,
        RequestPayer: Literal["requester"] = ...,
        BypassGovernanceRetention: bool = ...,
        ExpectedBucketOwner: str = ...,
        ChecksumAlgorithm: ChecksumAlgorithmType = ...,
    ) -> List[DeleteObjectsOutputTypeDef]:
        """
        Batch method.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#delete)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def limit(self, count: int) -> BucketObjectVersionsCollection:
        """
        Return at most this many ObjectVersions.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#limit)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def page_size(self, count: int) -> BucketObjectVersionsCollection:
        """
        Fetch at most this many ObjectVersions per service request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#page_size)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def pages(self) -> Iterator[List[ObjectVersion]]:
        """
        A generator which yields pages of ObjectVersions.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#pages)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

    def __iter__(self) -> Iterator[ObjectVersion]:
        """
        A generator which yields ObjectVersions.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/object_versions.html#__iter__)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject_versions)
        """

class BucketObjectsCollection(ResourceCollection):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#S3.Bucket.objects)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
    """
    def all(self) -> BucketObjectsCollection:
        """
        Get all items from the collection, optionally with a custom page size and item
        count limit.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#S3.Bucket.all)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def filter(  # type: ignore[override]
        self,
        *,
        Delimiter: str = ...,
        EncodingType: Literal["url"] = ...,
        Marker: str = ...,
        MaxKeys: int = ...,
        Prefix: str = ...,
        RequestPayer: Literal["requester"] = ...,
        ExpectedBucketOwner: str = ...,
        OptionalObjectAttributes: Sequence[Literal["RestoreStatus"]] = ...,
    ) -> BucketObjectsCollection:
        """
        Get items from the collection, passing keyword arguments along as parameters to
        the underlying service operation, which are typically used to filter the
        results.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#filter)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def delete(
        self,
        *,
        MFA: str = ...,
        RequestPayer: Literal["requester"] = ...,
        BypassGovernanceRetention: bool = ...,
        ExpectedBucketOwner: str = ...,
        ChecksumAlgorithm: ChecksumAlgorithmType = ...,
    ) -> List[DeleteObjectsOutputTypeDef]:
        """
        Batch method.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#delete)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def limit(self, count: int) -> BucketObjectsCollection:
        """
        Return at most this many ObjectSummarys.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#limit)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def page_size(self, count: int) -> BucketObjectsCollection:
        """
        Fetch at most this many ObjectSummarys per service request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#page_size)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def pages(self) -> Iterator[List[ObjectSummary]]:
        """
        A generator which yields pages of ObjectSummarys.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#pages)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

    def __iter__(self) -> Iterator[ObjectSummary]:
        """
        A generator which yields ObjectSummarys.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/objects.html#__iter__)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobjects)
        """

class MultipartUploadPartsCollection(ResourceCollection):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#S3.MultipartUpload.parts)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
    """
    def all(self) -> MultipartUploadPartsCollection:
        """
        Get all items from the collection, optionally with a custom page size and item
        count limit.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#S3.MultipartUpload.all)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

    def filter(  # type: ignore[override]
        self,
        *,
        MaxParts: int = ...,
        PartNumberMarker: int = ...,
        RequestPayer: Literal["requester"] = ...,
        ExpectedBucketOwner: str = ...,
        SSECustomerAlgorithm: str = ...,
        SSECustomerKey: str | bytes = ...,
    ) -> MultipartUploadPartsCollection:
        """
        Get items from the collection, passing keyword arguments along as parameters to
        the underlying service operation, which are typically used to filter the
        results.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#filter)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

    def limit(self, count: int) -> MultipartUploadPartsCollection:
        """
        Return at most this many MultipartUploadParts.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#limit)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

    def page_size(self, count: int) -> MultipartUploadPartsCollection:
        """
        Fetch at most this many MultipartUploadParts per service request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#page_size)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

    def pages(self) -> Iterator[List[MultipartUploadPart]]:
        """
        A generator which yields pages of MultipartUploadParts.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#pages)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

    def __iter__(self) -> Iterator[MultipartUploadPart]:
        """
        A generator which yields MultipartUploadParts.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/parts.html#__iter__)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadparts)
        """

class Bucket(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/index.html#S3.Bucket)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucket)
    """

    name: str
    multipart_uploads: BucketMultipartUploadsCollection
    object_versions: BucketObjectVersionsCollection
    objects: BucketObjectsCollection
    creation_date: datetime
    bucket_region: str
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this Bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketget_available_subresources-method)
        """

    def create(
        self, **kwargs: Unpack[CreateBucketRequestBucketCreateTypeDef]
    ) -> CreateBucketOutputTypeDef:
        """
        This action creates an Amazon S3 bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/create.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcreate-method)
        """

    def delete(self, **kwargs: Unpack[DeleteBucketRequestBucketDeleteTypeDef]) -> None:
        """
        Deletes the S3 bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketdelete-method)
        """

    def delete_objects(
        self, **kwargs: Unpack[DeleteObjectsRequestBucketDeleteObjectsTypeDef]
    ) -> DeleteObjectsOutputTypeDef:
        """
        This operation enables you to delete multiple objects from a bucket using a
        single HTTP request.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/delete_objects.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketdelete_objects-method)
        """

    def put_object(self, **kwargs: Unpack[PutObjectRequestBucketPutObjectTypeDef]) -> _Object:
        """
        Adds an object to a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/put_object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketput_object-method)
        """

    def wait_until_exists(self) -> None:
        """
        Waits until Bucket is exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/wait_until_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwait_until_exists-method)
        """

    def wait_until_not_exists(self) -> None:
        """
        Waits until Bucket is not_exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/wait_until_not_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwait_until_not_exists-method)
        """

    def Acl(self) -> _BucketAcl:
        """
        Creates a BucketAcl resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Acl.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketacl-method)
        """

    def Cors(self) -> _BucketCors:
        """
        Creates a BucketCors resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Cors.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcors-method)
        """

    def Lifecycle(self) -> _BucketLifecycle:
        """
        Creates a BucketLifecycle resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Lifecycle.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycle-method)
        """

    def LifecycleConfiguration(self) -> _BucketLifecycleConfiguration:
        """
        Creates a BucketLifecycleConfiguration resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/LifecycleConfiguration.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfiguration-method)
        """

    def Logging(self) -> _BucketLogging:
        """
        Creates a BucketLogging resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Logging.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlogging-method)
        """

    def Notification(self) -> _BucketNotification:
        """
        Creates a BucketNotification resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Notification.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotification-method)
        """

    def Object(self, key: str) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketobject-method)
        """

    def Policy(self) -> _BucketPolicy:
        """
        Creates a BucketPolicy resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Policy.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicy-method)
        """

    def RequestPayment(self) -> _BucketRequestPayment:
        """
        Creates a BucketRequestPayment resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/RequestPayment.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpayment-method)
        """

    def Tagging(self) -> _BucketTagging:
        """
        Creates a BucketTagging resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Tagging.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettagging-method)
        """

    def Versioning(self) -> _BucketVersioning:
        """
        Creates a BucketVersioning resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Versioning.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioning-method)
        """

    def Website(self) -> _BucketWebsite:
        """
        Creates a BucketWebsite resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/Website.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsite-method)
        """

    def load(self) -> None:
        """
        Calls s3.Client.list_buckets() to update the attributes of the Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketload-method)
        """

    def copy(
        self,
        CopySource: CopySourceTypeDef,
        Key: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        SourceClient: BaseClient | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Copy an object from one S3 location to another.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/copy.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcopy-method)
        """

    def download_file(
        self,
        Key: str,
        Filename: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Download an object from S3 to a file.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/download_file.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketdownload_file-method)
        """

    def download_fileobj(
        self,
        Key: str,
        Fileobj: FileobjTypeDef,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Download an object from S3 to a file-like object.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/download_fileobj.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketdownload_fileobj-method)
        """

    def upload_file(
        self,
        Filename: str,
        Key: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Upload a file to S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/upload_file.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketupload_file-method)
        """

    def upload_fileobj(
        self,
        Fileobj: FileobjTypeDef,
        Key: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Upload a file-like object to S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucket/upload_fileobj.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketupload_fileobj-method)
        """

_Bucket = Bucket

class BucketAcl(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/index.html#S3.BucketAcl)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketacl)
    """

    bucket_name: str
    owner: OwnerTypeDef
    grants: List[GrantTypeDef]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketAcl.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketaclget_available_subresources-method)
        """

    def put(self, **kwargs: Unpack[PutBucketAclRequestBucketAclPutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketaclput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketaclbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketaclload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketacl/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketaclreload-method)
        """

_BucketAcl = BucketAcl

class BucketCors(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/index.html#S3.BucketCors)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcors)
    """

    bucket_name: str
    cors_rules: List[CORSRuleOutputTypeDef]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketCors.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsget_available_subresources-method)
        """

    def delete(self, **kwargs: Unpack[DeleteBucketCorsRequestBucketCorsDeleteTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsdelete-method)
        """

    def put(self, **kwargs: Unpack[PutBucketCorsRequestBucketCorsPutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketcors/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketcorsreload-method)
        """

_BucketCors = BucketCors

class BucketLifecycle(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/index.html#S3.BucketLifecycle)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycle)
    """

    bucket_name: str
    rules: List[RuleOutputTypeDef]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketLifecycle.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleget_available_subresources-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteBucketLifecycleRequestBucketLifecycleDeleteTypeDef]
    ) -> None:
        """
        Deletes the lifecycle configuration from the specified bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycledelete-method)
        """

    def put(self, **kwargs: Unpack[PutBucketLifecycleRequestBucketLifecyclePutTypeDef]) -> None:
        """
        For an updated version of this API, see <a
        href="https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutBucketLifecycleConfiguration.html">PutBucketLifecycleConfiguration</a>.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecyclebucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycle/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecyclereload-method)
        """

_BucketLifecycle = BucketLifecycle

class BucketLifecycleConfiguration(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/index.html#S3.BucketLifecycleConfiguration)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfiguration)
    """

    bucket_name: str
    rules: List[LifecycleRuleOutputTypeDef]
    transition_default_minimum_object_size: TransitionDefaultMinimumObjectSizeType
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this
        BucketLifecycleConfiguration.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationget_available_subresources-method)
        """

    def delete(
        self,
        **kwargs: Unpack[DeleteBucketLifecycleRequestBucketLifecycleConfigurationDeleteTypeDef],
    ) -> None:
        """
        Deletes the lifecycle configuration from the specified bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationdelete-method)
        """

    def put(
        self,
        **kwargs: Unpack[
            PutBucketLifecycleConfigurationRequestBucketLifecycleConfigurationPutTypeDef
        ],
    ) -> PutBucketLifecycleConfigurationOutputTypeDef:
        """
        Creates a new lifecycle configuration for the bucket or replaces an existing
        lifecycle configuration.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlifecycleconfiguration/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlifecycleconfigurationreload-method)
        """

_BucketLifecycleConfiguration = BucketLifecycleConfiguration

class BucketLogging(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/index.html#S3.BucketLogging)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketlogging)
    """

    bucket_name: str
    logging_enabled: LoggingEnabledOutputTypeDef
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketLogging.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketloggingget_available_subresources-method)
        """

    def put(self, **kwargs: Unpack[PutBucketLoggingRequestBucketLoggingPutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketloggingput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketloggingbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketloggingload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketlogging/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketloggingreload-method)
        """

_BucketLogging = BucketLogging

class BucketNotification(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/index.html#S3.BucketNotification)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotification)
    """

    bucket_name: str
    topic_configurations: List[TopicConfigurationOutputTypeDef]
    queue_configurations: List[QueueConfigurationOutputTypeDef]
    lambda_function_configurations: List[LambdaFunctionConfigurationOutputTypeDef]
    event_bridge_configuration: Dict[str, Any]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketNotification.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotificationget_available_subresources-method)
        """

    def put(
        self,
        **kwargs: Unpack[PutBucketNotificationConfigurationRequestBucketNotificationPutTypeDef],
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotificationput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotificationbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotificationload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketnotification/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketnotificationreload-method)
        """

_BucketNotification = BucketNotification

class BucketPolicy(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/index.html#S3.BucketPolicy)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicy)
    """

    bucket_name: str
    policy: str
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketPolicy.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicyget_available_subresources-method)
        """

    def delete(self, **kwargs: Unpack[DeleteBucketPolicyRequestBucketPolicyDeleteTypeDef]) -> None:
        """
        Deletes the policy of a specified bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicydelete-method)
        """

    def put(self, **kwargs: Unpack[PutBucketPolicyRequestBucketPolicyPutTypeDef]) -> None:
        """
        Applies an Amazon S3 bucket policy to an Amazon S3 bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicyput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicybucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicyload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketpolicy/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketpolicyreload-method)
        """

_BucketPolicy = BucketPolicy

class BucketRequestPayment(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/index.html#S3.BucketRequestPayment)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpayment)
    """

    bucket_name: str
    payer: PayerType
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketRequestPayment.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpaymentget_available_subresources-method)
        """

    def put(
        self, **kwargs: Unpack[PutBucketRequestPaymentRequestBucketRequestPaymentPutTypeDef]
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpaymentput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpaymentbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpaymentload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketrequestpayment/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketrequestpaymentreload-method)
        """

_BucketRequestPayment = BucketRequestPayment

class BucketTagging(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/index.html#S3.BucketTagging)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettagging)
    """

    bucket_name: str
    tag_set: List[TagTypeDef]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketTagging.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingget_available_subresources-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteBucketTaggingRequestBucketTaggingDeleteTypeDef]
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingdelete-method)
        """

    def put(self, **kwargs: Unpack[PutBucketTaggingRequestBucketTaggingPutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/buckettagging/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#buckettaggingreload-method)
        """

_BucketTagging = BucketTagging

class BucketVersioning(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/index.html#S3.BucketVersioning)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioning)
    """

    bucket_name: str
    status: BucketVersioningStatusType
    mfa_delete: MFADeleteStatusType
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketVersioning.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningget_available_subresources-method)
        """

    def enable(
        self, **kwargs: Unpack[PutBucketVersioningRequestBucketVersioningEnableTypeDef]
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/enable.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningenable-method)
        """

    def put(self, **kwargs: Unpack[PutBucketVersioningRequestBucketVersioningPutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningput-method)
        """

    def suspend(
        self, **kwargs: Unpack[PutBucketVersioningRequestBucketVersioningSuspendTypeDef]
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/suspend.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningsuspend-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningbucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketversioning/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketversioningreload-method)
        """

_BucketVersioning = BucketVersioning

class BucketWebsite(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/index.html#S3.BucketWebsite)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsite)
    """

    bucket_name: str
    redirect_all_requests_to: RedirectAllRequestsToTypeDef
    index_document: IndexDocumentTypeDef
    error_document: ErrorDocumentTypeDef
    routing_rules: List[RoutingRuleTypeDef]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this BucketWebsite.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsiteget_available_subresources-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteBucketWebsiteRequestBucketWebsiteDeleteTypeDef]
    ) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsitedelete-method)
        """

    def put(self, **kwargs: Unpack[PutBucketWebsiteRequestBucketWebsitePutTypeDef]) -> None:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsiteput-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsitebucket-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsiteload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/bucketwebsite/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#bucketwebsitereload-method)
        """

_BucketWebsite = BucketWebsite

class MultipartUpload(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/index.html#S3.MultipartUpload)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartupload)
    """

    bucket_name: str
    object_key: str
    id: str
    parts: MultipartUploadPartsCollection
    upload_id: str
    key: str
    initiated: datetime
    storage_class: StorageClassType
    owner: OwnerTypeDef
    initiator: InitiatorTypeDef
    checksum_algorithm: ChecksumAlgorithmType
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this MultipartUpload.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadget_available_subresources-method)
        """

    def abort(
        self, **kwargs: Unpack[AbortMultipartUploadRequestMultipartUploadAbortTypeDef]
    ) -> AbortMultipartUploadOutputTypeDef:
        """
        This operation aborts a multipart upload.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/abort.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadabort-method)
        """

    def complete(
        self, **kwargs: Unpack[CompleteMultipartUploadRequestMultipartUploadCompleteTypeDef]
    ) -> _Object:
        """
        Completes a multipart upload by assembling previously uploaded parts.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/complete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadcomplete-method)
        """

    def Object(self) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadobject-method)
        """

    def Part(self, part_number: int) -> _MultipartUploadPart:
        """
        Creates a MultipartUploadPart resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartupload/Part.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpart-method)
        """

_MultipartUpload = MultipartUpload

class MultipartUploadPart(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartuploadpart/index.html#S3.MultipartUploadPart)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpart)
    """

    bucket_name: str
    object_key: str
    multipart_upload_id: str
    part_number: int
    last_modified: datetime
    e_tag: str
    size: int
    checksum_crc32: str
    checksum_crc32_c: str
    checksum_sha1: str
    checksum_sha256: str
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this MultipartUploadPart.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartuploadpart/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpartget_available_subresources-method)
        """

    def copy_from(
        self, **kwargs: Unpack[UploadPartCopyRequestMultipartUploadPartCopyFromTypeDef]
    ) -> UploadPartCopyOutputTypeDef:
        """
        Uploads a part by copying data from an existing object as data source.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartuploadpart/copy_from.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpartcopy_from-method)
        """

    def upload(
        self, **kwargs: Unpack[UploadPartRequestMultipartUploadPartUploadTypeDef]
    ) -> UploadPartOutputTypeDef:
        """
        Uploads a part in a multipart upload.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartuploadpart/upload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpartupload-method)
        """

    def MultipartUpload(self) -> _MultipartUpload:
        """
        Creates a MultipartUpload resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/multipartuploadpart/MultipartUpload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#multipartuploadpartmultipartupload-method)
        """

_MultipartUploadPart = MultipartUploadPart

class Object(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/index.html#S3.Object)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#object)
    """

    bucket_name: str
    key: str
    delete_marker: bool
    accept_ranges: str
    expiration: str
    restore: str
    archive_status: ArchiveStatusType
    last_modified: datetime
    content_length: int
    checksum_crc32: str
    checksum_crc32_c: str
    checksum_sha1: str
    checksum_sha256: str
    e_tag: str
    missing_meta: int
    version_id: str
    cache_control: str
    content_disposition: str
    content_encoding: str
    content_language: str
    content_type: str
    expires: datetime
    website_redirect_location: str
    server_side_encryption: ServerSideEncryptionType
    metadata: Dict[str, str]
    sse_customer_algorithm: str
    sse_customer_key_md5: str
    ssekms_key_id: str
    bucket_key_enabled: bool
    storage_class: StorageClassType
    request_charged: Literal["requester"]
    replication_status: ReplicationStatusType
    parts_count: int
    object_lock_mode: ObjectLockModeType
    object_lock_retain_until_date: datetime
    object_lock_legal_hold_status: ObjectLockLegalHoldStatusType
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this Object.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectget_available_subresources-method)
        """

    def copy_from(
        self, **kwargs: Unpack[CopyObjectRequestObjectCopyFromTypeDef]
    ) -> CopyObjectOutputTypeDef:
        """
        Creates a copy of an object that is already stored in Amazon S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/copy_from.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectcopy_from-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteObjectRequestObjectDeleteTypeDef]
    ) -> DeleteObjectOutputTypeDef:
        """
        Removes an object from a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectdelete-method)
        """

    def get(self, **kwargs: Unpack[GetObjectRequestObjectGetTypeDef]) -> GetObjectOutputTypeDef:
        """
        Retrieves an object from Amazon S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/get.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectget-method)
        """

    def initiate_multipart_upload(
        self, **kwargs: Unpack[CreateMultipartUploadRequestObjectInitiateMultipartUploadTypeDef]
    ) -> _MultipartUpload:
        """
        This action initiates a multipart upload and returns an upload ID.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/initiate_multipart_upload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectinitiate_multipart_upload-method)
        """

    def put(self, **kwargs: Unpack[PutObjectRequestObjectPutTypeDef]) -> PutObjectOutputTypeDef:
        """
        Adds an object to a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectput-method)
        """

    def restore_object(
        self, **kwargs: Unpack[RestoreObjectRequestObjectRestoreObjectTypeDef]
    ) -> RestoreObjectOutputTypeDef:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/restore_object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectrestore_object-method)
        """

    def wait_until_exists(self) -> None:
        """
        Waits until Object is exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/wait_until_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectwait_until_exists-method)
        """

    def wait_until_not_exists(self) -> None:
        """
        Waits until Object is not_exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/wait_until_not_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectwait_until_not_exists-method)
        """

    def Acl(self) -> _ObjectAcl:
        """
        Creates a ObjectAcl resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/Acl.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectacl-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectbucket-method)
        """

    def MultipartUpload(self, id: str) -> _MultipartUpload:
        """
        Creates a MultipartUpload resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/MultipartUpload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectmultipartupload-method)
        """

    def Version(self, id: str) -> _ObjectVersion:
        """
        Creates a ObjectVersion resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/Version.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversion-method)
        """

    def copy(
        self,
        CopySource: CopySourceTypeDef,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        SourceClient: BaseClient | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Copy an object from one S3 location to another.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/copy.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectcopy-method)
        """

    def download_file(
        self,
        Filename: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Download an object from S3 to a file.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/download_file.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectdownload_file-method)
        """

    def download_fileobj(
        self,
        Fileobj: FileobjTypeDef,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Download an object from S3 to a file-like object.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/download_fileobj.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectdownload_fileobj-method)
        """

    def upload_file(
        self,
        Filename: str,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Upload a file to S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/upload_file.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectupload_file-method)
        """

    def upload_fileobj(
        self,
        Fileobj: FileobjTypeDef,
        ExtraArgs: Dict[str, Any] | None = ...,
        Callback: Callable[..., Any] | None = ...,
        Config: TransferConfig | None = ...,
    ) -> None:
        """
        Upload a file-like object to S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/upload_fileobj.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectupload_fileobj-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/object/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectreload-method)
        """

_Object = Object

class ObjectAcl(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/index.html#S3.ObjectAcl)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectacl)
    """

    bucket_name: str
    object_key: str
    owner: OwnerTypeDef
    grants: List[GrantTypeDef]
    request_charged: Literal["requester"]
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this ObjectAcl.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectaclget_available_subresources-method)
        """

    def put(
        self, **kwargs: Unpack[PutObjectAclRequestObjectAclPutTypeDef]
    ) -> PutObjectAclOutputTypeDef:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectaclput-method)
        """

    def Object(self) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectaclobject-method)
        """

    def load(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectaclload-method)
        """

    def reload(self) -> None:
        """
        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectacl/reload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectaclreload-method)
        """

_ObjectAcl = ObjectAcl

class ObjectSummary(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/index.html#S3.ObjectSummary)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummary)
    """

    bucket_name: str
    key: str
    last_modified: datetime
    e_tag: str
    checksum_algorithm: List[ChecksumAlgorithmType]
    size: int
    storage_class: ObjectStorageClassType
    owner: OwnerTypeDef
    restore_status: RestoreStatusTypeDef
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this ObjectSummary.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryget_available_subresources-method)
        """

    def copy_from(
        self, **kwargs: Unpack[CopyObjectRequestObjectSummaryCopyFromTypeDef]
    ) -> CopyObjectOutputTypeDef:
        """
        Creates a copy of an object that is already stored in Amazon S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/copy_from.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarycopy_from-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteObjectRequestObjectSummaryDeleteTypeDef]
    ) -> DeleteObjectOutputTypeDef:
        """
        Removes an object from a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarydelete-method)
        """

    def get(
        self, **kwargs: Unpack[GetObjectRequestObjectSummaryGetTypeDef]
    ) -> GetObjectOutputTypeDef:
        """
        Retrieves an object from Amazon S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/get.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryget-method)
        """

    def initiate_multipart_upload(
        self,
        **kwargs: Unpack[CreateMultipartUploadRequestObjectSummaryInitiateMultipartUploadTypeDef],
    ) -> _MultipartUpload:
        """
        This action initiates a multipart upload and returns an upload ID.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/initiate_multipart_upload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryinitiate_multipart_upload-method)
        """

    def put(
        self, **kwargs: Unpack[PutObjectRequestObjectSummaryPutTypeDef]
    ) -> PutObjectOutputTypeDef:
        """
        Adds an object to a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/put.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryput-method)
        """

    def restore_object(
        self, **kwargs: Unpack[RestoreObjectRequestObjectSummaryRestoreObjectTypeDef]
    ) -> RestoreObjectOutputTypeDef:
        """
        This operation is not supported for directory buckets.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/restore_object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryrestore_object-method)
        """

    def wait_until_exists(self) -> None:
        """
        Waits until ObjectSummary is exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/wait_until_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarywait_until_exists-method)
        """

    def wait_until_not_exists(self) -> None:
        """
        Waits until ObjectSummary is not_exists.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/wait_until_not_exists.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarywait_until_not_exists-method)
        """

    def Acl(self) -> _ObjectAcl:
        """
        Creates a ObjectAcl resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/Acl.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryacl-method)
        """

    def Bucket(self) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarybucket-method)
        """

    def MultipartUpload(self, id: str) -> _MultipartUpload:
        """
        Creates a MultipartUpload resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/MultipartUpload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummarymultipartupload-method)
        """

    def Object(self) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryobject-method)
        """

    def Version(self, id: str) -> _ObjectVersion:
        """
        Creates a ObjectVersion resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/Version.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryversion-method)
        """

    def load(self) -> None:
        """
        Calls s3.Client.head_object to update the attributes of the ObjectSummary
        resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectsummary/load.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectsummaryload-method)
        """

_ObjectSummary = ObjectSummary

class ObjectVersion(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/index.html#S3.ObjectVersion)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversion)
    """

    bucket_name: str
    object_key: str
    id: str
    e_tag: str
    checksum_algorithm: List[ChecksumAlgorithmType]
    size: int
    storage_class: Literal["STANDARD"]
    key: str
    version_id: str
    is_latest: bool
    last_modified: datetime
    owner: OwnerTypeDef
    restore_status: RestoreStatusTypeDef
    meta: S3ResourceMeta  # type: ignore[override]

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this ObjectVersion.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversionget_available_subresources-method)
        """

    def delete(
        self, **kwargs: Unpack[DeleteObjectRequestObjectVersionDeleteTypeDef]
    ) -> DeleteObjectOutputTypeDef:
        """
        Removes an object from a bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/delete.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversiondelete-method)
        """

    def get(
        self, **kwargs: Unpack[GetObjectRequestObjectVersionGetTypeDef]
    ) -> GetObjectOutputTypeDef:
        """
        Retrieves an object from Amazon S3.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/get.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversionget-method)
        """

    def head(
        self, **kwargs: Unpack[HeadObjectRequestObjectVersionHeadTypeDef]
    ) -> HeadObjectOutputTypeDef:
        """
        The <code>HEAD</code> operation retrieves metadata from an object without
        returning the object itself.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/head.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversionhead-method)
        """

    def Object(self) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/objectversion/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#objectversionobject-method)
        """

_ObjectVersion = ObjectVersion

class S3ResourceMeta(ResourceMeta):
    client: S3Client  # type: ignore[override]

class S3ServiceResource(ServiceResource):
    """
    [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/index.html)
    [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/)
    """

    meta: S3ResourceMeta  # type: ignore[override]
    buckets: ServiceResourceBucketsCollection

    def get_available_subresources(self) -> Sequence[str]:
        """
        Returns a list of all the available sub-resources for this resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/get_available_subresources.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourceget_available_subresources-method)
        """

    def create_bucket(
        self, **kwargs: Unpack[CreateBucketRequestServiceResourceCreateBucketTypeDef]
    ) -> _Bucket:
        """
        This action creates an Amazon S3 bucket.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/create_bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcecreate_bucket-method)
        """

    def Bucket(self, name: str) -> _Bucket:
        """
        Creates a Bucket resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/Bucket.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucket-method)
        """

    def BucketAcl(self, bucket_name: str) -> _BucketAcl:
        """
        Creates a BucketAcl resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketAcl.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketacl-method)
        """

    def BucketCors(self, bucket_name: str) -> _BucketCors:
        """
        Creates a BucketCors resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketCors.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketcors-method)
        """

    def BucketLifecycle(self, bucket_name: str) -> _BucketLifecycle:
        """
        Creates a BucketLifecycle resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketLifecycle.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketlifecycle-method)
        """

    def BucketLifecycleConfiguration(self, bucket_name: str) -> _BucketLifecycleConfiguration:
        """
        Creates a BucketLifecycleConfiguration resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketLifecycleConfiguration.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketlifecycleconfiguration-method)
        """

    def BucketLogging(self, bucket_name: str) -> _BucketLogging:
        """
        Creates a BucketLogging resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketLogging.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketlogging-method)
        """

    def BucketNotification(self, bucket_name: str) -> _BucketNotification:
        """
        Creates a BucketNotification resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketNotification.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketnotification-method)
        """

    def BucketPolicy(self, bucket_name: str) -> _BucketPolicy:
        """
        Creates a BucketPolicy resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketPolicy.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketpolicy-method)
        """

    def BucketRequestPayment(self, bucket_name: str) -> _BucketRequestPayment:
        """
        Creates a BucketRequestPayment resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketRequestPayment.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketrequestpayment-method)
        """

    def BucketTagging(self, bucket_name: str) -> _BucketTagging:
        """
        Creates a BucketTagging resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketTagging.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebuckettagging-method)
        """

    def BucketVersioning(self, bucket_name: str) -> _BucketVersioning:
        """
        Creates a BucketVersioning resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketVersioning.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketversioning-method)
        """

    def BucketWebsite(self, bucket_name: str) -> _BucketWebsite:
        """
        Creates a BucketWebsite resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/BucketWebsite.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcebucketwebsite-method)
        """

    def MultipartUpload(self, bucket_name: str, object_key: str, id: str) -> _MultipartUpload:
        """
        Creates a MultipartUpload resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/MultipartUpload.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcemultipartupload-method)
        """

    def MultipartUploadPart(
        self, bucket_name: str, object_key: str, multipart_upload_id: str, part_number: int
    ) -> _MultipartUploadPart:
        """
        Creates a MultipartUploadPart resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/MultipartUploadPart.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourcemultipartuploadpart-method)
        """

    def Object(self, bucket_name: str, key: str) -> _Object:
        """
        Creates a Object resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/Object.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourceobject-method)
        """

    def ObjectAcl(self, bucket_name: str, object_key: str) -> _ObjectAcl:
        """
        Creates a ObjectAcl resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/ObjectAcl.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourceobjectacl-method)
        """

    def ObjectSummary(self, bucket_name: str, key: str) -> _ObjectSummary:
        """
        Creates a ObjectSummary resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/ObjectSummary.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourceobjectsummary-method)
        """

    def ObjectVersion(self, bucket_name: str, object_key: str, id: str) -> _ObjectVersion:
        """
        Creates a ObjectVersion resource.

        [Show boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/service-resource/ObjectVersion.html)
        [Show boto3-stubs documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/#s3serviceresourceobjectversion-method)
        """
