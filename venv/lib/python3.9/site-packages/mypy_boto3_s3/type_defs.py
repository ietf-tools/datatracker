"""
Type annotations for s3 service type definitions.

[Documentation](https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/type_defs/)

Usage::

    ```python
    from mypy_boto3_s3.type_defs import AbortIncompleteMultipartUploadTypeDef

    data: AbortIncompleteMultipartUploadTypeDef = ...
    ```

Copyright 2025 Vlad Emelianov
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import IO, Any, Union

from boto3.s3.transfer import TransferConfig
from botocore.client import BaseClient
from botocore.eventstream import EventStream
from botocore.response import StreamingBody

from .literals import (
    ArchiveStatusType,
    BucketAccelerateStatusType,
    BucketCannedACLType,
    BucketLocationConstraintType,
    BucketLogsPermissionType,
    BucketVersioningStatusType,
    ChecksumAlgorithmType,
    CompressionTypeType,
    DataRedundancyType,
    DeleteMarkerReplicationStatusType,
    EventType,
    ExistingObjectReplicationStatusType,
    ExpirationStatusType,
    FileHeaderInfoType,
    FilterRuleNameType,
    IntelligentTieringAccessTierType,
    IntelligentTieringStatusType,
    InventoryFormatType,
    InventoryFrequencyType,
    InventoryIncludedObjectVersionsType,
    InventoryOptionalFieldType,
    JSONTypeType,
    LocationTypeType,
    MetadataDirectiveType,
    MetricsStatusType,
    MFADeleteStatusType,
    MFADeleteType,
    ObjectAttributesType,
    ObjectCannedACLType,
    ObjectLockLegalHoldStatusType,
    ObjectLockModeType,
    ObjectLockRetentionModeType,
    ObjectOwnershipType,
    ObjectStorageClassType,
    PartitionDateSourceType,
    PayerType,
    PermissionType,
    ProtocolType,
    QuoteFieldsType,
    ReplicaModificationsStatusType,
    ReplicationRuleStatusType,
    ReplicationStatusType,
    ReplicationTimeStatusType,
    ServerSideEncryptionType,
    SessionModeType,
    SseKmsEncryptedObjectsStatusType,
    StorageClassType,
    TaggingDirectiveType,
    TierType,
    TransitionDefaultMinimumObjectSizeType,
    TransitionStorageClassType,
    TypeType,
)

if sys.version_info >= (3, 9):
    from builtins import dict as Dict
    from builtins import list as List
    from collections.abc import Callable, Mapping, Sequence
else:
    from typing import Callable, Dict, List, Mapping, Sequence
if sys.version_info >= (3, 12):
    from typing import Literal, NotRequired, TypedDict
else:
    from typing_extensions import Literal, NotRequired, TypedDict


__all__ = (
    "AbortIncompleteMultipartUploadTypeDef",
    "AbortMultipartUploadOutputTypeDef",
    "AbortMultipartUploadRequestMultipartUploadAbortTypeDef",
    "AbortMultipartUploadRequestRequestTypeDef",
    "AccelerateConfigurationTypeDef",
    "AccessControlPolicyTypeDef",
    "AccessControlTranslationTypeDef",
    "AnalyticsAndOperatorOutputTypeDef",
    "AnalyticsAndOperatorTypeDef",
    "AnalyticsAndOperatorUnionTypeDef",
    "AnalyticsConfigurationOutputTypeDef",
    "AnalyticsConfigurationTypeDef",
    "AnalyticsExportDestinationTypeDef",
    "AnalyticsFilterOutputTypeDef",
    "AnalyticsFilterTypeDef",
    "AnalyticsFilterUnionTypeDef",
    "AnalyticsS3BucketDestinationTypeDef",
    "BlobTypeDef",
    "BucketCopyRequestTypeDef",
    "BucketDownloadFileRequestTypeDef",
    "BucketDownloadFileobjRequestTypeDef",
    "BucketInfoTypeDef",
    "BucketLifecycleConfigurationTypeDef",
    "BucketLoggingStatusTypeDef",
    "BucketTypeDef",
    "BucketUploadFileRequestTypeDef",
    "BucketUploadFileobjRequestTypeDef",
    "CORSConfigurationTypeDef",
    "CORSRuleOutputTypeDef",
    "CORSRuleTypeDef",
    "CSVInputTypeDef",
    "CSVOutputTypeDef",
    "ChecksumTypeDef",
    "ClientCopyRequestTypeDef",
    "ClientDownloadFileRequestTypeDef",
    "ClientDownloadFileobjRequestTypeDef",
    "ClientGeneratePresignedPostRequestTypeDef",
    "ClientUploadFileRequestTypeDef",
    "ClientUploadFileobjRequestTypeDef",
    "CloudFunctionConfigurationOutputTypeDef",
    "CloudFunctionConfigurationTypeDef",
    "CloudFunctionConfigurationUnionTypeDef",
    "CommonPrefixTypeDef",
    "CompleteMultipartUploadOutputTypeDef",
    "CompleteMultipartUploadRequestMultipartUploadCompleteTypeDef",
    "CompleteMultipartUploadRequestRequestTypeDef",
    "CompletedMultipartUploadTypeDef",
    "CompletedPartTypeDef",
    "ConditionTypeDef",
    "CopyObjectOutputTypeDef",
    "CopyObjectRequestObjectCopyFromTypeDef",
    "CopyObjectRequestObjectSummaryCopyFromTypeDef",
    "CopyObjectRequestRequestTypeDef",
    "CopyObjectResultTypeDef",
    "CopyPartResultTypeDef",
    "CopySourceOrStrTypeDef",
    "CopySourceTypeDef",
    "CreateBucketConfigurationTypeDef",
    "CreateBucketMetadataTableConfigurationRequestRequestTypeDef",
    "CreateBucketOutputTypeDef",
    "CreateBucketRequestBucketCreateTypeDef",
    "CreateBucketRequestRequestTypeDef",
    "CreateBucketRequestServiceResourceCreateBucketTypeDef",
    "CreateMultipartUploadOutputTypeDef",
    "CreateMultipartUploadRequestObjectInitiateMultipartUploadTypeDef",
    "CreateMultipartUploadRequestObjectSummaryInitiateMultipartUploadTypeDef",
    "CreateMultipartUploadRequestRequestTypeDef",
    "CreateSessionOutputTypeDef",
    "CreateSessionRequestRequestTypeDef",
    "DefaultRetentionTypeDef",
    "DeleteBucketAnalyticsConfigurationRequestRequestTypeDef",
    "DeleteBucketCorsRequestBucketCorsDeleteTypeDef",
    "DeleteBucketCorsRequestRequestTypeDef",
    "DeleteBucketEncryptionRequestRequestTypeDef",
    "DeleteBucketIntelligentTieringConfigurationRequestRequestTypeDef",
    "DeleteBucketInventoryConfigurationRequestRequestTypeDef",
    "DeleteBucketLifecycleRequestBucketLifecycleConfigurationDeleteTypeDef",
    "DeleteBucketLifecycleRequestBucketLifecycleDeleteTypeDef",
    "DeleteBucketLifecycleRequestRequestTypeDef",
    "DeleteBucketMetadataTableConfigurationRequestRequestTypeDef",
    "DeleteBucketMetricsConfigurationRequestRequestTypeDef",
    "DeleteBucketOwnershipControlsRequestRequestTypeDef",
    "DeleteBucketPolicyRequestBucketPolicyDeleteTypeDef",
    "DeleteBucketPolicyRequestRequestTypeDef",
    "DeleteBucketReplicationRequestRequestTypeDef",
    "DeleteBucketRequestBucketDeleteTypeDef",
    "DeleteBucketRequestRequestTypeDef",
    "DeleteBucketTaggingRequestBucketTaggingDeleteTypeDef",
    "DeleteBucketTaggingRequestRequestTypeDef",
    "DeleteBucketWebsiteRequestBucketWebsiteDeleteTypeDef",
    "DeleteBucketWebsiteRequestRequestTypeDef",
    "DeleteMarkerEntryTypeDef",
    "DeleteMarkerReplicationTypeDef",
    "DeleteObjectOutputTypeDef",
    "DeleteObjectRequestObjectDeleteTypeDef",
    "DeleteObjectRequestObjectSummaryDeleteTypeDef",
    "DeleteObjectRequestObjectVersionDeleteTypeDef",
    "DeleteObjectRequestRequestTypeDef",
    "DeleteObjectTaggingOutputTypeDef",
    "DeleteObjectTaggingRequestRequestTypeDef",
    "DeleteObjectsOutputTypeDef",
    "DeleteObjectsRequestBucketDeleteObjectsTypeDef",
    "DeleteObjectsRequestRequestTypeDef",
    "DeletePublicAccessBlockRequestRequestTypeDef",
    "DeleteTypeDef",
    "DeletedObjectTypeDef",
    "DestinationTypeDef",
    "EmptyResponseMetadataTypeDef",
    "EncryptionConfigurationTypeDef",
    "EncryptionTypeDef",
    "ErrorDetailsTypeDef",
    "ErrorDocumentTypeDef",
    "ErrorTypeDef",
    "ExistingObjectReplicationTypeDef",
    "FileobjTypeDef",
    "FilterRuleTypeDef",
    "GetBucketAccelerateConfigurationOutputTypeDef",
    "GetBucketAccelerateConfigurationRequestRequestTypeDef",
    "GetBucketAclOutputTypeDef",
    "GetBucketAclRequestRequestTypeDef",
    "GetBucketAnalyticsConfigurationOutputTypeDef",
    "GetBucketAnalyticsConfigurationRequestRequestTypeDef",
    "GetBucketCorsOutputTypeDef",
    "GetBucketCorsRequestRequestTypeDef",
    "GetBucketEncryptionOutputTypeDef",
    "GetBucketEncryptionRequestRequestTypeDef",
    "GetBucketIntelligentTieringConfigurationOutputTypeDef",
    "GetBucketIntelligentTieringConfigurationRequestRequestTypeDef",
    "GetBucketInventoryConfigurationOutputTypeDef",
    "GetBucketInventoryConfigurationRequestRequestTypeDef",
    "GetBucketLifecycleConfigurationOutputTypeDef",
    "GetBucketLifecycleConfigurationRequestRequestTypeDef",
    "GetBucketLifecycleOutputTypeDef",
    "GetBucketLifecycleRequestRequestTypeDef",
    "GetBucketLocationOutputTypeDef",
    "GetBucketLocationRequestRequestTypeDef",
    "GetBucketLoggingOutputTypeDef",
    "GetBucketLoggingRequestRequestTypeDef",
    "GetBucketMetadataTableConfigurationOutputTypeDef",
    "GetBucketMetadataTableConfigurationRequestRequestTypeDef",
    "GetBucketMetadataTableConfigurationResultTypeDef",
    "GetBucketMetricsConfigurationOutputTypeDef",
    "GetBucketMetricsConfigurationRequestRequestTypeDef",
    "GetBucketNotificationConfigurationRequestRequestTypeDef",
    "GetBucketOwnershipControlsOutputTypeDef",
    "GetBucketOwnershipControlsRequestRequestTypeDef",
    "GetBucketPolicyOutputTypeDef",
    "GetBucketPolicyRequestRequestTypeDef",
    "GetBucketPolicyStatusOutputTypeDef",
    "GetBucketPolicyStatusRequestRequestTypeDef",
    "GetBucketReplicationOutputTypeDef",
    "GetBucketReplicationRequestRequestTypeDef",
    "GetBucketRequestPaymentOutputTypeDef",
    "GetBucketRequestPaymentRequestRequestTypeDef",
    "GetBucketTaggingOutputTypeDef",
    "GetBucketTaggingRequestRequestTypeDef",
    "GetBucketVersioningOutputTypeDef",
    "GetBucketVersioningRequestRequestTypeDef",
    "GetBucketWebsiteOutputTypeDef",
    "GetBucketWebsiteRequestRequestTypeDef",
    "GetObjectAclOutputTypeDef",
    "GetObjectAclRequestRequestTypeDef",
    "GetObjectAttributesOutputTypeDef",
    "GetObjectAttributesPartsTypeDef",
    "GetObjectAttributesRequestRequestTypeDef",
    "GetObjectLegalHoldOutputTypeDef",
    "GetObjectLegalHoldRequestRequestTypeDef",
    "GetObjectLockConfigurationOutputTypeDef",
    "GetObjectLockConfigurationRequestRequestTypeDef",
    "GetObjectOutputTypeDef",
    "GetObjectRequestObjectGetTypeDef",
    "GetObjectRequestObjectSummaryGetTypeDef",
    "GetObjectRequestObjectVersionGetTypeDef",
    "GetObjectRequestRequestTypeDef",
    "GetObjectRetentionOutputTypeDef",
    "GetObjectRetentionRequestRequestTypeDef",
    "GetObjectTaggingOutputTypeDef",
    "GetObjectTaggingRequestRequestTypeDef",
    "GetObjectTorrentOutputTypeDef",
    "GetObjectTorrentRequestRequestTypeDef",
    "GetPublicAccessBlockOutputTypeDef",
    "GetPublicAccessBlockRequestRequestTypeDef",
    "GlacierJobParametersTypeDef",
    "GrantTypeDef",
    "GranteeTypeDef",
    "HeadBucketOutputTypeDef",
    "HeadBucketRequestRequestTypeDef",
    "HeadBucketRequestWaitTypeDef",
    "HeadObjectOutputTypeDef",
    "HeadObjectRequestObjectVersionHeadTypeDef",
    "HeadObjectRequestRequestTypeDef",
    "HeadObjectRequestWaitTypeDef",
    "IndexDocumentTypeDef",
    "InitiatorTypeDef",
    "InputSerializationTypeDef",
    "IntelligentTieringAndOperatorOutputTypeDef",
    "IntelligentTieringAndOperatorTypeDef",
    "IntelligentTieringAndOperatorUnionTypeDef",
    "IntelligentTieringConfigurationOutputTypeDef",
    "IntelligentTieringConfigurationTypeDef",
    "IntelligentTieringFilterOutputTypeDef",
    "IntelligentTieringFilterTypeDef",
    "IntelligentTieringFilterUnionTypeDef",
    "InventoryConfigurationOutputTypeDef",
    "InventoryConfigurationTypeDef",
    "InventoryDestinationOutputTypeDef",
    "InventoryDestinationTypeDef",
    "InventoryDestinationUnionTypeDef",
    "InventoryEncryptionOutputTypeDef",
    "InventoryEncryptionTypeDef",
    "InventoryEncryptionUnionTypeDef",
    "InventoryFilterTypeDef",
    "InventoryS3BucketDestinationOutputTypeDef",
    "InventoryS3BucketDestinationTypeDef",
    "InventoryS3BucketDestinationUnionTypeDef",
    "InventoryScheduleTypeDef",
    "JSONInputTypeDef",
    "JSONOutputTypeDef",
    "LambdaFunctionConfigurationOutputTypeDef",
    "LambdaFunctionConfigurationTypeDef",
    "LifecycleConfigurationTypeDef",
    "LifecycleExpirationOutputTypeDef",
    "LifecycleExpirationTypeDef",
    "LifecycleRuleAndOperatorOutputTypeDef",
    "LifecycleRuleAndOperatorTypeDef",
    "LifecycleRuleFilterOutputTypeDef",
    "LifecycleRuleFilterTypeDef",
    "LifecycleRuleOutputTypeDef",
    "LifecycleRuleTypeDef",
    "ListBucketAnalyticsConfigurationsOutputTypeDef",
    "ListBucketAnalyticsConfigurationsRequestRequestTypeDef",
    "ListBucketIntelligentTieringConfigurationsOutputTypeDef",
    "ListBucketIntelligentTieringConfigurationsRequestRequestTypeDef",
    "ListBucketInventoryConfigurationsOutputTypeDef",
    "ListBucketInventoryConfigurationsRequestRequestTypeDef",
    "ListBucketMetricsConfigurationsOutputTypeDef",
    "ListBucketMetricsConfigurationsRequestRequestTypeDef",
    "ListBucketsOutputTypeDef",
    "ListBucketsRequestPaginateTypeDef",
    "ListBucketsRequestRequestTypeDef",
    "ListDirectoryBucketsOutputTypeDef",
    "ListDirectoryBucketsRequestPaginateTypeDef",
    "ListDirectoryBucketsRequestRequestTypeDef",
    "ListMultipartUploadsOutputTypeDef",
    "ListMultipartUploadsRequestPaginateTypeDef",
    "ListMultipartUploadsRequestRequestTypeDef",
    "ListObjectVersionsOutputTypeDef",
    "ListObjectVersionsRequestPaginateTypeDef",
    "ListObjectVersionsRequestRequestTypeDef",
    "ListObjectsOutputTypeDef",
    "ListObjectsRequestPaginateTypeDef",
    "ListObjectsRequestRequestTypeDef",
    "ListObjectsV2OutputTypeDef",
    "ListObjectsV2RequestPaginateTypeDef",
    "ListObjectsV2RequestRequestTypeDef",
    "ListPartsOutputTypeDef",
    "ListPartsRequestPaginateTypeDef",
    "ListPartsRequestRequestTypeDef",
    "LocationInfoTypeDef",
    "LoggingEnabledOutputTypeDef",
    "LoggingEnabledTypeDef",
    "MetadataEntryTypeDef",
    "MetadataTableConfigurationResultTypeDef",
    "MetadataTableConfigurationTypeDef",
    "MetricsAndOperatorOutputTypeDef",
    "MetricsAndOperatorTypeDef",
    "MetricsAndOperatorUnionTypeDef",
    "MetricsConfigurationOutputTypeDef",
    "MetricsConfigurationTypeDef",
    "MetricsFilterOutputTypeDef",
    "MetricsFilterTypeDef",
    "MetricsFilterUnionTypeDef",
    "MetricsTypeDef",
    "MultipartUploadTypeDef",
    "NoncurrentVersionExpirationTypeDef",
    "NoncurrentVersionTransitionTypeDef",
    "NotificationConfigurationDeprecatedResponseTypeDef",
    "NotificationConfigurationDeprecatedTypeDef",
    "NotificationConfigurationFilterOutputTypeDef",
    "NotificationConfigurationFilterTypeDef",
    "NotificationConfigurationResponseTypeDef",
    "NotificationConfigurationTypeDef",
    "ObjectCopyRequestTypeDef",
    "ObjectDownloadFileRequestTypeDef",
    "ObjectDownloadFileobjRequestTypeDef",
    "ObjectIdentifierTypeDef",
    "ObjectLockConfigurationTypeDef",
    "ObjectLockLegalHoldTypeDef",
    "ObjectLockRetentionOutputTypeDef",
    "ObjectLockRetentionTypeDef",
    "ObjectLockRuleTypeDef",
    "ObjectPartTypeDef",
    "ObjectTypeDef",
    "ObjectUploadFileRequestTypeDef",
    "ObjectUploadFileobjRequestTypeDef",
    "ObjectVersionTypeDef",
    "OutputLocationTypeDef",
    "OutputSerializationTypeDef",
    "OwnerTypeDef",
    "OwnershipControlsOutputTypeDef",
    "OwnershipControlsRuleTypeDef",
    "OwnershipControlsTypeDef",
    "PaginatorConfigTypeDef",
    "PartTypeDef",
    "PartitionedPrefixTypeDef",
    "PolicyStatusTypeDef",
    "ProgressEventTypeDef",
    "ProgressTypeDef",
    "PublicAccessBlockConfigurationTypeDef",
    "PutBucketAccelerateConfigurationRequestRequestTypeDef",
    "PutBucketAclRequestBucketAclPutTypeDef",
    "PutBucketAclRequestRequestTypeDef",
    "PutBucketAnalyticsConfigurationRequestRequestTypeDef",
    "PutBucketCorsRequestBucketCorsPutTypeDef",
    "PutBucketCorsRequestRequestTypeDef",
    "PutBucketEncryptionRequestRequestTypeDef",
    "PutBucketIntelligentTieringConfigurationRequestRequestTypeDef",
    "PutBucketInventoryConfigurationRequestRequestTypeDef",
    "PutBucketLifecycleConfigurationOutputTypeDef",
    "PutBucketLifecycleConfigurationRequestBucketLifecycleConfigurationPutTypeDef",
    "PutBucketLifecycleConfigurationRequestRequestTypeDef",
    "PutBucketLifecycleRequestBucketLifecyclePutTypeDef",
    "PutBucketLifecycleRequestRequestTypeDef",
    "PutBucketLoggingRequestBucketLoggingPutTypeDef",
    "PutBucketLoggingRequestRequestTypeDef",
    "PutBucketMetricsConfigurationRequestRequestTypeDef",
    "PutBucketNotificationConfigurationRequestBucketNotificationPutTypeDef",
    "PutBucketNotificationConfigurationRequestRequestTypeDef",
    "PutBucketNotificationRequestRequestTypeDef",
    "PutBucketOwnershipControlsRequestRequestTypeDef",
    "PutBucketPolicyRequestBucketPolicyPutTypeDef",
    "PutBucketPolicyRequestRequestTypeDef",
    "PutBucketReplicationRequestRequestTypeDef",
    "PutBucketRequestPaymentRequestBucketRequestPaymentPutTypeDef",
    "PutBucketRequestPaymentRequestRequestTypeDef",
    "PutBucketTaggingRequestBucketTaggingPutTypeDef",
    "PutBucketTaggingRequestRequestTypeDef",
    "PutBucketVersioningRequestBucketVersioningEnableTypeDef",
    "PutBucketVersioningRequestBucketVersioningPutTypeDef",
    "PutBucketVersioningRequestBucketVersioningSuspendTypeDef",
    "PutBucketVersioningRequestRequestTypeDef",
    "PutBucketWebsiteRequestBucketWebsitePutTypeDef",
    "PutBucketWebsiteRequestRequestTypeDef",
    "PutObjectAclOutputTypeDef",
    "PutObjectAclRequestObjectAclPutTypeDef",
    "PutObjectAclRequestRequestTypeDef",
    "PutObjectLegalHoldOutputTypeDef",
    "PutObjectLegalHoldRequestRequestTypeDef",
    "PutObjectLockConfigurationOutputTypeDef",
    "PutObjectLockConfigurationRequestRequestTypeDef",
    "PutObjectOutputTypeDef",
    "PutObjectRequestBucketPutObjectTypeDef",
    "PutObjectRequestObjectPutTypeDef",
    "PutObjectRequestObjectSummaryPutTypeDef",
    "PutObjectRequestRequestTypeDef",
    "PutObjectRetentionOutputTypeDef",
    "PutObjectRetentionRequestRequestTypeDef",
    "PutObjectTaggingOutputTypeDef",
    "PutObjectTaggingRequestRequestTypeDef",
    "PutPublicAccessBlockRequestRequestTypeDef",
    "QueueConfigurationDeprecatedOutputTypeDef",
    "QueueConfigurationDeprecatedTypeDef",
    "QueueConfigurationDeprecatedUnionTypeDef",
    "QueueConfigurationOutputTypeDef",
    "QueueConfigurationTypeDef",
    "RecordsEventTypeDef",
    "RedirectAllRequestsToTypeDef",
    "RedirectTypeDef",
    "ReplicaModificationsTypeDef",
    "ReplicationConfigurationOutputTypeDef",
    "ReplicationConfigurationTypeDef",
    "ReplicationRuleAndOperatorOutputTypeDef",
    "ReplicationRuleAndOperatorTypeDef",
    "ReplicationRuleAndOperatorUnionTypeDef",
    "ReplicationRuleFilterOutputTypeDef",
    "ReplicationRuleFilterTypeDef",
    "ReplicationRuleFilterUnionTypeDef",
    "ReplicationRuleOutputTypeDef",
    "ReplicationRuleTypeDef",
    "ReplicationRuleUnionTypeDef",
    "ReplicationTimeTypeDef",
    "ReplicationTimeValueTypeDef",
    "RequestPaymentConfigurationTypeDef",
    "RequestProgressTypeDef",
    "ResponseMetadataTypeDef",
    "RestoreObjectOutputTypeDef",
    "RestoreObjectRequestObjectRestoreObjectTypeDef",
    "RestoreObjectRequestObjectSummaryRestoreObjectTypeDef",
    "RestoreObjectRequestRequestTypeDef",
    "RestoreRequestTypeDef",
    "RestoreStatusTypeDef",
    "RoutingRuleTypeDef",
    "RuleOutputTypeDef",
    "RuleTypeDef",
    "S3KeyFilterOutputTypeDef",
    "S3KeyFilterTypeDef",
    "S3LocationTypeDef",
    "S3TablesDestinationResultTypeDef",
    "S3TablesDestinationTypeDef",
    "SSEKMSTypeDef",
    "ScanRangeTypeDef",
    "SelectObjectContentEventStreamTypeDef",
    "SelectObjectContentOutputTypeDef",
    "SelectObjectContentRequestRequestTypeDef",
    "SelectParametersTypeDef",
    "ServerSideEncryptionByDefaultTypeDef",
    "ServerSideEncryptionConfigurationOutputTypeDef",
    "ServerSideEncryptionConfigurationTypeDef",
    "ServerSideEncryptionRuleTypeDef",
    "SessionCredentialsTypeDef",
    "SourceSelectionCriteriaTypeDef",
    "SseKmsEncryptedObjectsTypeDef",
    "StatsEventTypeDef",
    "StatsTypeDef",
    "StorageClassAnalysisDataExportTypeDef",
    "StorageClassAnalysisTypeDef",
    "TagTypeDef",
    "TaggingTypeDef",
    "TargetGrantTypeDef",
    "TargetObjectKeyFormatOutputTypeDef",
    "TargetObjectKeyFormatTypeDef",
    "TieringTypeDef",
    "TimestampTypeDef",
    "TopicConfigurationDeprecatedOutputTypeDef",
    "TopicConfigurationDeprecatedTypeDef",
    "TopicConfigurationDeprecatedUnionTypeDef",
    "TopicConfigurationOutputTypeDef",
    "TopicConfigurationTypeDef",
    "TransitionOutputTypeDef",
    "TransitionTypeDef",
    "UploadPartCopyOutputTypeDef",
    "UploadPartCopyRequestMultipartUploadPartCopyFromTypeDef",
    "UploadPartCopyRequestRequestTypeDef",
    "UploadPartOutputTypeDef",
    "UploadPartRequestMultipartUploadPartUploadTypeDef",
    "UploadPartRequestRequestTypeDef",
    "VersioningConfigurationTypeDef",
    "WaiterConfigTypeDef",
    "WebsiteConfigurationTypeDef",
    "WriteGetObjectResponseRequestRequestTypeDef",
)


class AbortIncompleteMultipartUploadTypeDef(TypedDict):
    DaysAfterInitiation: NotRequired[int]


class ResponseMetadataTypeDef(TypedDict):
    RequestId: str
    HTTPStatusCode: int
    HTTPHeaders: Dict[str, str]
    RetryAttempts: int
    HostId: NotRequired[str]


TimestampTypeDef = Union[datetime, str]


class AccelerateConfigurationTypeDef(TypedDict):
    Status: NotRequired[BucketAccelerateStatusType]


class OwnerTypeDef(TypedDict):
    DisplayName: NotRequired[str]
    ID: NotRequired[str]


class AccessControlTranslationTypeDef(TypedDict):
    Owner: Literal["Destination"]


class TagTypeDef(TypedDict):
    Key: str
    Value: str


class AnalyticsS3BucketDestinationTypeDef(TypedDict):
    Format: Literal["CSV"]
    Bucket: str
    BucketAccountId: NotRequired[str]
    Prefix: NotRequired[str]


BlobTypeDef = Union[str, bytes, IO[Any], StreamingBody]


class CopySourceTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]


class BucketDownloadFileRequestTypeDef(TypedDict):
    Key: str
    Filename: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


FileobjTypeDef = Union[IO[Any], StreamingBody]
BucketInfoTypeDef = TypedDict(
    "BucketInfoTypeDef",
    {
        "DataRedundancy": NotRequired[DataRedundancyType],
        "Type": NotRequired[Literal["Directory"]],
    },
)


class BucketTypeDef(TypedDict):
    Name: NotRequired[str]
    CreationDate: NotRequired[datetime]
    BucketRegion: NotRequired[str]


class BucketUploadFileRequestTypeDef(TypedDict):
    Filename: str
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class CORSRuleTypeDef(TypedDict):
    AllowedMethods: Sequence[str]
    AllowedOrigins: Sequence[str]
    ID: NotRequired[str]
    AllowedHeaders: NotRequired[Sequence[str]]
    ExposeHeaders: NotRequired[Sequence[str]]
    MaxAgeSeconds: NotRequired[int]


class CORSRuleOutputTypeDef(TypedDict):
    AllowedMethods: List[str]
    AllowedOrigins: List[str]
    ID: NotRequired[str]
    AllowedHeaders: NotRequired[List[str]]
    ExposeHeaders: NotRequired[List[str]]
    MaxAgeSeconds: NotRequired[int]


class CSVInputTypeDef(TypedDict):
    FileHeaderInfo: NotRequired[FileHeaderInfoType]
    Comments: NotRequired[str]
    QuoteEscapeCharacter: NotRequired[str]
    RecordDelimiter: NotRequired[str]
    FieldDelimiter: NotRequired[str]
    QuoteCharacter: NotRequired[str]
    AllowQuotedRecordDelimiter: NotRequired[bool]


class CSVOutputTypeDef(TypedDict):
    QuoteFields: NotRequired[QuoteFieldsType]
    QuoteEscapeCharacter: NotRequired[str]
    RecordDelimiter: NotRequired[str]
    FieldDelimiter: NotRequired[str]
    QuoteCharacter: NotRequired[str]


class ChecksumTypeDef(TypedDict):
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]


class ClientDownloadFileRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Filename: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ClientGeneratePresignedPostRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Fields: NotRequired[Dict[str, Any] | None]
    Conditions: NotRequired[List[Any] | Dict[str, Any] | None]
    ExpiresIn: NotRequired[int]


class ClientUploadFileRequestTypeDef(TypedDict):
    Filename: str
    Bucket: str
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class CloudFunctionConfigurationOutputTypeDef(TypedDict):
    Id: NotRequired[str]
    Event: NotRequired[EventType]
    Events: NotRequired[List[EventType]]
    CloudFunction: NotRequired[str]
    InvocationRole: NotRequired[str]


class CloudFunctionConfigurationTypeDef(TypedDict):
    Id: NotRequired[str]
    Event: NotRequired[EventType]
    Events: NotRequired[Sequence[EventType]]
    CloudFunction: NotRequired[str]
    InvocationRole: NotRequired[str]


class CommonPrefixTypeDef(TypedDict):
    Prefix: NotRequired[str]


class CompletedPartTypeDef(TypedDict):
    ETag: NotRequired[str]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    PartNumber: NotRequired[int]


class ConditionTypeDef(TypedDict):
    HttpErrorCodeReturnedEquals: NotRequired[str]
    KeyPrefixEquals: NotRequired[str]


class CopyObjectResultTypeDef(TypedDict):
    ETag: NotRequired[str]
    LastModified: NotRequired[datetime]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]


class CopyPartResultTypeDef(TypedDict):
    ETag: NotRequired[str]
    LastModified: NotRequired[datetime]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]


LocationInfoTypeDef = TypedDict(
    "LocationInfoTypeDef",
    {
        "Type": NotRequired[LocationTypeType],
        "Name": NotRequired[str],
    },
)


class SessionCredentialsTypeDef(TypedDict):
    AccessKeyId: str
    SecretAccessKey: str
    SessionToken: str
    Expiration: datetime


class CreateSessionRequestRequestTypeDef(TypedDict):
    Bucket: str
    SessionMode: NotRequired[SessionModeType]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]


class DefaultRetentionTypeDef(TypedDict):
    Mode: NotRequired[ObjectLockRetentionModeType]
    Days: NotRequired[int]
    Years: NotRequired[int]


class DeleteBucketAnalyticsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketCorsRequestBucketCorsDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketCorsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketEncryptionRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketIntelligentTieringConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str


class DeleteBucketInventoryConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketLifecycleRequestBucketLifecycleConfigurationDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketLifecycleRequestBucketLifecycleDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketLifecycleRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketMetadataTableConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketMetricsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketOwnershipControlsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketPolicyRequestBucketPolicyDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketPolicyRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketReplicationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketRequestBucketDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketTaggingRequestBucketTaggingDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketWebsiteRequestBucketWebsiteDeleteTypeDef(TypedDict):
    ExpectedBucketOwner: NotRequired[str]


class DeleteBucketWebsiteRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class DeleteMarkerReplicationTypeDef(TypedDict):
    Status: NotRequired[DeleteMarkerReplicationStatusType]


class DeleteObjectTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class DeletedObjectTypeDef(TypedDict):
    Key: NotRequired[str]
    VersionId: NotRequired[str]
    DeleteMarker: NotRequired[bool]
    DeleteMarkerVersionId: NotRequired[str]


class ErrorTypeDef(TypedDict):
    Key: NotRequired[str]
    VersionId: NotRequired[str]
    Code: NotRequired[str]
    Message: NotRequired[str]


class DeletePublicAccessBlockRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class EncryptionConfigurationTypeDef(TypedDict):
    ReplicaKmsKeyID: NotRequired[str]


class EncryptionTypeDef(TypedDict):
    EncryptionType: ServerSideEncryptionType
    KMSKeyId: NotRequired[str]
    KMSContext: NotRequired[str]


class ErrorDetailsTypeDef(TypedDict):
    ErrorCode: NotRequired[str]
    ErrorMessage: NotRequired[str]


class ErrorDocumentTypeDef(TypedDict):
    Key: str


class ExistingObjectReplicationTypeDef(TypedDict):
    Status: ExistingObjectReplicationStatusType


class FilterRuleTypeDef(TypedDict):
    Name: NotRequired[FilterRuleNameType]
    Value: NotRequired[str]


class GetBucketAccelerateConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]


class GetBucketAclRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketAnalyticsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketCorsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketEncryptionRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketIntelligentTieringConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str


class GetBucketInventoryConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketLifecycleConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketLifecycleRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketLocationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketLoggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketMetadataTableConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketMetricsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketNotificationConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketOwnershipControlsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketPolicyRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class PolicyStatusTypeDef(TypedDict):
    IsPublic: NotRequired[bool]


class GetBucketPolicyStatusRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketReplicationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketRequestPaymentRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetBucketVersioningRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class IndexDocumentTypeDef(TypedDict):
    Suffix: str


RedirectAllRequestsToTypeDef = TypedDict(
    "RedirectAllRequestsToTypeDef",
    {
        "HostName": str,
        "Protocol": NotRequired[ProtocolType],
    },
)


class GetBucketWebsiteRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GetObjectAclRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class ObjectPartTypeDef(TypedDict):
    PartNumber: NotRequired[int]
    Size: NotRequired[int]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]


class GetObjectAttributesRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    ObjectAttributes: Sequence[ObjectAttributesType]
    VersionId: NotRequired[str]
    MaxParts: NotRequired[int]
    PartNumberMarker: NotRequired[int]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class ObjectLockLegalHoldTypeDef(TypedDict):
    Status: NotRequired[ObjectLockLegalHoldStatusType]


class GetObjectLegalHoldRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class GetObjectLockConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class ObjectLockRetentionOutputTypeDef(TypedDict):
    Mode: NotRequired[ObjectLockRetentionModeType]
    RetainUntilDate: NotRequired[datetime]


class GetObjectRetentionRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class GetObjectTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]


class GetObjectTorrentRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class PublicAccessBlockConfigurationTypeDef(TypedDict):
    BlockPublicAcls: NotRequired[bool]
    IgnorePublicAcls: NotRequired[bool]
    BlockPublicPolicy: NotRequired[bool]
    RestrictPublicBuckets: NotRequired[bool]


class GetPublicAccessBlockRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class GlacierJobParametersTypeDef(TypedDict):
    Tier: TierType


GranteeTypeDef = TypedDict(
    "GranteeTypeDef",
    {
        "Type": TypeType,
        "DisplayName": NotRequired[str],
        "EmailAddress": NotRequired[str],
        "ID": NotRequired[str],
        "URI": NotRequired[str],
    },
)


class HeadBucketRequestRequestTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]


class WaiterConfigTypeDef(TypedDict):
    Delay: NotRequired[int]
    MaxAttempts: NotRequired[int]


class InitiatorTypeDef(TypedDict):
    ID: NotRequired[str]
    DisplayName: NotRequired[str]


JSONInputTypeDef = TypedDict(
    "JSONInputTypeDef",
    {
        "Type": NotRequired[JSONTypeType],
    },
)


class TieringTypeDef(TypedDict):
    Days: int
    AccessTier: IntelligentTieringAccessTierType


class InventoryFilterTypeDef(TypedDict):
    Prefix: str


class InventoryScheduleTypeDef(TypedDict):
    Frequency: InventoryFrequencyType


class SSEKMSTypeDef(TypedDict):
    KeyId: str


class JSONOutputTypeDef(TypedDict):
    RecordDelimiter: NotRequired[str]


class LifecycleExpirationOutputTypeDef(TypedDict):
    Date: NotRequired[datetime]
    Days: NotRequired[int]
    ExpiredObjectDeleteMarker: NotRequired[bool]


class NoncurrentVersionExpirationTypeDef(TypedDict):
    NoncurrentDays: NotRequired[int]
    NewerNoncurrentVersions: NotRequired[int]


class NoncurrentVersionTransitionTypeDef(TypedDict):
    NoncurrentDays: NotRequired[int]
    StorageClass: NotRequired[TransitionStorageClassType]
    NewerNoncurrentVersions: NotRequired[int]


class TransitionOutputTypeDef(TypedDict):
    Date: NotRequired[datetime]
    Days: NotRequired[int]
    StorageClass: NotRequired[TransitionStorageClassType]


class ListBucketAnalyticsConfigurationsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ContinuationToken: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class ListBucketIntelligentTieringConfigurationsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ContinuationToken: NotRequired[str]


class ListBucketInventoryConfigurationsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ContinuationToken: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class ListBucketMetricsConfigurationsRequestRequestTypeDef(TypedDict):
    Bucket: str
    ContinuationToken: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PaginatorConfigTypeDef(TypedDict):
    MaxItems: NotRequired[int]
    PageSize: NotRequired[int]
    StartingToken: NotRequired[str]


class ListBucketsRequestRequestTypeDef(TypedDict):
    MaxBuckets: NotRequired[int]
    ContinuationToken: NotRequired[str]
    Prefix: NotRequired[str]
    BucketRegion: NotRequired[str]


class ListDirectoryBucketsRequestRequestTypeDef(TypedDict):
    ContinuationToken: NotRequired[str]
    MaxDirectoryBuckets: NotRequired[int]


class ListMultipartUploadsRequestRequestTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    KeyMarker: NotRequired[str]
    MaxUploads: NotRequired[int]
    Prefix: NotRequired[str]
    UploadIdMarker: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]


class ListObjectVersionsRequestRequestTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    KeyMarker: NotRequired[str]
    MaxKeys: NotRequired[int]
    Prefix: NotRequired[str]
    VersionIdMarker: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]


class ListObjectsRequestRequestTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    Marker: NotRequired[str]
    MaxKeys: NotRequired[int]
    Prefix: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]


class ListObjectsV2RequestRequestTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    MaxKeys: NotRequired[int]
    Prefix: NotRequired[str]
    ContinuationToken: NotRequired[str]
    FetchOwner: NotRequired[bool]
    StartAfter: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]


class PartTypeDef(TypedDict):
    PartNumber: NotRequired[int]
    LastModified: NotRequired[datetime]
    ETag: NotRequired[str]
    Size: NotRequired[int]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]


class ListPartsRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    UploadId: str
    MaxParts: NotRequired[int]
    PartNumberMarker: NotRequired[int]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]


class MetadataEntryTypeDef(TypedDict):
    Name: NotRequired[str]
    Value: NotRequired[str]


class S3TablesDestinationResultTypeDef(TypedDict):
    TableBucketArn: str
    TableName: str
    TableArn: str
    TableNamespace: str


class S3TablesDestinationTypeDef(TypedDict):
    TableBucketArn: str
    TableName: str


class ReplicationTimeValueTypeDef(TypedDict):
    Minutes: NotRequired[int]


class QueueConfigurationDeprecatedOutputTypeDef(TypedDict):
    Id: NotRequired[str]
    Event: NotRequired[EventType]
    Events: NotRequired[List[EventType]]
    Queue: NotRequired[str]


class TopicConfigurationDeprecatedOutputTypeDef(TypedDict):
    Id: NotRequired[str]
    Events: NotRequired[List[EventType]]
    Event: NotRequired[EventType]
    Topic: NotRequired[str]


class ObjectDownloadFileRequestTypeDef(TypedDict):
    Filename: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class RestoreStatusTypeDef(TypedDict):
    IsRestoreInProgress: NotRequired[bool]
    RestoreExpiryDate: NotRequired[datetime]


class ObjectUploadFileRequestTypeDef(TypedDict):
    Filename: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class OwnershipControlsRuleTypeDef(TypedDict):
    ObjectOwnership: ObjectOwnershipType


class PartitionedPrefixTypeDef(TypedDict):
    PartitionDateSource: NotRequired[PartitionDateSourceType]


class ProgressTypeDef(TypedDict):
    BytesScanned: NotRequired[int]
    BytesProcessed: NotRequired[int]
    BytesReturned: NotRequired[int]


class PutBucketPolicyRequestBucketPolicyPutTypeDef(TypedDict):
    Policy: str
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ConfirmRemoveSelfBucketAccess: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketPolicyRequestRequestTypeDef(TypedDict):
    Bucket: str
    Policy: str
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ConfirmRemoveSelfBucketAccess: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]


class RequestPaymentConfigurationTypeDef(TypedDict):
    Payer: PayerType


class PutBucketVersioningRequestBucketVersioningEnableTypeDef(TypedDict):
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    MFA: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class VersioningConfigurationTypeDef(TypedDict):
    MFADelete: NotRequired[MFADeleteType]
    Status: NotRequired[BucketVersioningStatusType]


class PutBucketVersioningRequestBucketVersioningSuspendTypeDef(TypedDict):
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    MFA: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class QueueConfigurationDeprecatedTypeDef(TypedDict):
    Id: NotRequired[str]
    Event: NotRequired[EventType]
    Events: NotRequired[Sequence[EventType]]
    Queue: NotRequired[str]


class RecordsEventTypeDef(TypedDict):
    Payload: NotRequired[bytes]


RedirectTypeDef = TypedDict(
    "RedirectTypeDef",
    {
        "HostName": NotRequired[str],
        "HttpRedirectCode": NotRequired[str],
        "Protocol": NotRequired[ProtocolType],
        "ReplaceKeyPrefixWith": NotRequired[str],
        "ReplaceKeyWith": NotRequired[str],
    },
)


class ReplicaModificationsTypeDef(TypedDict):
    Status: ReplicaModificationsStatusType


class RequestProgressTypeDef(TypedDict):
    Enabled: NotRequired[bool]


class ScanRangeTypeDef(TypedDict):
    Start: NotRequired[int]
    End: NotRequired[int]


class ServerSideEncryptionByDefaultTypeDef(TypedDict):
    SSEAlgorithm: ServerSideEncryptionType
    KMSMasterKeyID: NotRequired[str]


class SseKmsEncryptedObjectsTypeDef(TypedDict):
    Status: SseKmsEncryptedObjectsStatusType


class StatsTypeDef(TypedDict):
    BytesScanned: NotRequired[int]
    BytesProcessed: NotRequired[int]
    BytesReturned: NotRequired[int]


class TopicConfigurationDeprecatedTypeDef(TypedDict):
    Id: NotRequired[str]
    Events: NotRequired[Sequence[EventType]]
    Event: NotRequired[EventType]
    Topic: NotRequired[str]


class AbortMultipartUploadOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class CompleteMultipartUploadOutputTypeDef(TypedDict):
    Location: str
    Bucket: str
    Key: str
    Expiration: str
    ETag: str
    ChecksumCRC32: str
    ChecksumCRC32C: str
    ChecksumSHA1: str
    ChecksumSHA256: str
    ServerSideEncryption: ServerSideEncryptionType
    VersionId: str
    SSEKMSKeyId: str
    BucketKeyEnabled: bool
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class CreateBucketOutputTypeDef(TypedDict):
    Location: str
    ResponseMetadata: ResponseMetadataTypeDef


class CreateMultipartUploadOutputTypeDef(TypedDict):
    AbortDate: datetime
    AbortRuleId: str
    Bucket: str
    Key: str
    UploadId: str
    ServerSideEncryption: ServerSideEncryptionType
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    SSEKMSEncryptionContext: str
    BucketKeyEnabled: bool
    RequestCharged: Literal["requester"]
    ChecksumAlgorithm: ChecksumAlgorithmType
    ResponseMetadata: ResponseMetadataTypeDef


class DeleteObjectOutputTypeDef(TypedDict):
    DeleteMarker: bool
    VersionId: str
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class DeleteObjectTaggingOutputTypeDef(TypedDict):
    VersionId: str
    ResponseMetadata: ResponseMetadataTypeDef


class EmptyResponseMetadataTypeDef(TypedDict):
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketAccelerateConfigurationOutputTypeDef(TypedDict):
    Status: BucketAccelerateStatusType
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketLocationOutputTypeDef(TypedDict):
    LocationConstraint: BucketLocationConstraintType
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketPolicyOutputTypeDef(TypedDict):
    Policy: str
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketRequestPaymentOutputTypeDef(TypedDict):
    Payer: PayerType
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketVersioningOutputTypeDef(TypedDict):
    Status: BucketVersioningStatusType
    MFADelete: MFADeleteStatusType
    ResponseMetadata: ResponseMetadataTypeDef


class GetObjectOutputTypeDef(TypedDict):
    Body: StreamingBody
    DeleteMarker: bool
    AcceptRanges: str
    Expiration: str
    Restore: str
    LastModified: datetime
    ContentLength: int
    ETag: str
    ChecksumCRC32: str
    ChecksumCRC32C: str
    ChecksumSHA1: str
    ChecksumSHA256: str
    MissingMeta: int
    VersionId: str
    CacheControl: str
    ContentDisposition: str
    ContentEncoding: str
    ContentLanguage: str
    ContentRange: str
    ContentType: str
    Expires: datetime
    WebsiteRedirectLocation: str
    ServerSideEncryption: ServerSideEncryptionType
    Metadata: Dict[str, str]
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    BucketKeyEnabled: bool
    StorageClass: StorageClassType
    RequestCharged: Literal["requester"]
    ReplicationStatus: ReplicationStatusType
    PartsCount: int
    TagCount: int
    ObjectLockMode: ObjectLockModeType
    ObjectLockRetainUntilDate: datetime
    ObjectLockLegalHoldStatus: ObjectLockLegalHoldStatusType
    ResponseMetadata: ResponseMetadataTypeDef


class GetObjectTorrentOutputTypeDef(TypedDict):
    Body: StreamingBody
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class HeadBucketOutputTypeDef(TypedDict):
    BucketLocationType: LocationTypeType
    BucketLocationName: str
    BucketRegion: str
    AccessPointAlias: bool
    ResponseMetadata: ResponseMetadataTypeDef


class HeadObjectOutputTypeDef(TypedDict):
    DeleteMarker: bool
    AcceptRanges: str
    Expiration: str
    Restore: str
    ArchiveStatus: ArchiveStatusType
    LastModified: datetime
    ContentLength: int
    ChecksumCRC32: str
    ChecksumCRC32C: str
    ChecksumSHA1: str
    ChecksumSHA256: str
    ETag: str
    MissingMeta: int
    VersionId: str
    CacheControl: str
    ContentDisposition: str
    ContentEncoding: str
    ContentLanguage: str
    ContentType: str
    Expires: datetime
    WebsiteRedirectLocation: str
    ServerSideEncryption: ServerSideEncryptionType
    Metadata: Dict[str, str]
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    BucketKeyEnabled: bool
    StorageClass: StorageClassType
    RequestCharged: Literal["requester"]
    ReplicationStatus: ReplicationStatusType
    PartsCount: int
    ObjectLockMode: ObjectLockModeType
    ObjectLockRetainUntilDate: datetime
    ObjectLockLegalHoldStatus: ObjectLockLegalHoldStatusType
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketLifecycleConfigurationOutputTypeDef(TypedDict):
    TransitionDefaultMinimumObjectSize: TransitionDefaultMinimumObjectSizeType
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectAclOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectLegalHoldOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectLockConfigurationOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectOutputTypeDef(TypedDict):
    Expiration: str
    ETag: str
    ChecksumCRC32: str
    ChecksumCRC32C: str
    ChecksumSHA1: str
    ChecksumSHA256: str
    ServerSideEncryption: ServerSideEncryptionType
    VersionId: str
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    SSEKMSEncryptionContext: str
    BucketKeyEnabled: bool
    Size: int
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectRetentionOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectTaggingOutputTypeDef(TypedDict):
    VersionId: str
    ResponseMetadata: ResponseMetadataTypeDef


class RestoreObjectOutputTypeDef(TypedDict):
    RequestCharged: Literal["requester"]
    RestoreOutputPath: str
    ResponseMetadata: ResponseMetadataTypeDef


class UploadPartOutputTypeDef(TypedDict):
    ServerSideEncryption: ServerSideEncryptionType
    ETag: str
    ChecksumCRC32: str
    ChecksumCRC32C: str
    ChecksumSHA1: str
    ChecksumSHA256: str
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    BucketKeyEnabled: bool
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class AbortMultipartUploadRequestMultipartUploadAbortTypeDef(TypedDict):
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    IfMatchInitiatedTime: NotRequired[TimestampTypeDef]


class AbortMultipartUploadRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    UploadId: str
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    IfMatchInitiatedTime: NotRequired[TimestampTypeDef]


class CreateMultipartUploadRequestObjectInitiateMultipartUploadTypeDef(TypedDict):
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class CreateMultipartUploadRequestObjectSummaryInitiateMultipartUploadTypeDef(TypedDict):
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class CreateMultipartUploadRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class DeleteObjectRequestObjectDeleteTypeDef(TypedDict):
    MFA: NotRequired[str]
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfMatchLastModifiedTime: NotRequired[TimestampTypeDef]
    IfMatchSize: NotRequired[int]


class DeleteObjectRequestObjectSummaryDeleteTypeDef(TypedDict):
    MFA: NotRequired[str]
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfMatchLastModifiedTime: NotRequired[TimestampTypeDef]
    IfMatchSize: NotRequired[int]


class DeleteObjectRequestObjectVersionDeleteTypeDef(TypedDict):
    MFA: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfMatchLastModifiedTime: NotRequired[TimestampTypeDef]
    IfMatchSize: NotRequired[int]


class DeleteObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    MFA: NotRequired[str]
    VersionId: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfMatchLastModifiedTime: NotRequired[TimestampTypeDef]
    IfMatchSize: NotRequired[int]


class GetObjectRequestObjectGetTypeDef(TypedDict):
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    VersionId: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class GetObjectRequestObjectSummaryGetTypeDef(TypedDict):
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    VersionId: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class GetObjectRequestObjectVersionGetTypeDef(TypedDict):
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class GetObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    VersionId: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class HeadObjectRequestObjectVersionHeadTypeDef(TypedDict):
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class HeadObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    VersionId: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]


class LifecycleExpirationTypeDef(TypedDict):
    Date: NotRequired[TimestampTypeDef]
    Days: NotRequired[int]
    ExpiredObjectDeleteMarker: NotRequired[bool]


class ObjectIdentifierTypeDef(TypedDict):
    Key: str
    VersionId: NotRequired[str]
    ETag: NotRequired[str]
    LastModifiedTime: NotRequired[TimestampTypeDef]
    Size: NotRequired[int]


class ObjectLockRetentionTypeDef(TypedDict):
    Mode: NotRequired[ObjectLockRetentionModeType]
    RetainUntilDate: NotRequired[TimestampTypeDef]


class TransitionTypeDef(TypedDict):
    Date: NotRequired[TimestampTypeDef]
    Days: NotRequired[int]
    StorageClass: NotRequired[TransitionStorageClassType]


class PutBucketAccelerateConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    AccelerateConfiguration: AccelerateConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class DeleteMarkerEntryTypeDef(TypedDict):
    Owner: NotRequired[OwnerTypeDef]
    Key: NotRequired[str]
    VersionId: NotRequired[str]
    IsLatest: NotRequired[bool]
    LastModified: NotRequired[datetime]


class AnalyticsAndOperatorOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[List[TagTypeDef]]


class AnalyticsAndOperatorTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[Sequence[TagTypeDef]]


class GetBucketTaggingOutputTypeDef(TypedDict):
    TagSet: List[TagTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class GetObjectTaggingOutputTypeDef(TypedDict):
    VersionId: str
    TagSet: List[TagTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class IntelligentTieringAndOperatorOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[List[TagTypeDef]]


class IntelligentTieringAndOperatorTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[Sequence[TagTypeDef]]


class LifecycleRuleAndOperatorOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[List[TagTypeDef]]
    ObjectSizeGreaterThan: NotRequired[int]
    ObjectSizeLessThan: NotRequired[int]


class LifecycleRuleAndOperatorTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[Sequence[TagTypeDef]]
    ObjectSizeGreaterThan: NotRequired[int]
    ObjectSizeLessThan: NotRequired[int]


class MetricsAndOperatorOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[List[TagTypeDef]]
    AccessPointArn: NotRequired[str]


class MetricsAndOperatorTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[Sequence[TagTypeDef]]
    AccessPointArn: NotRequired[str]


class ReplicationRuleAndOperatorOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[List[TagTypeDef]]


class ReplicationRuleAndOperatorTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tags: NotRequired[Sequence[TagTypeDef]]


class TaggingTypeDef(TypedDict):
    TagSet: Sequence[TagTypeDef]


class AnalyticsExportDestinationTypeDef(TypedDict):
    S3BucketDestination: AnalyticsS3BucketDestinationTypeDef


class PutObjectRequestBucketPutObjectTypeDef(TypedDict):
    Key: str
    ACL: NotRequired[ObjectCannedACLType]
    Body: NotRequired[BlobTypeDef]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ContentType: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    WriteOffsetBytes: NotRequired[int]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectRequestObjectPutTypeDef(TypedDict):
    ACL: NotRequired[ObjectCannedACLType]
    Body: NotRequired[BlobTypeDef]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ContentType: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    WriteOffsetBytes: NotRequired[int]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectRequestObjectSummaryPutTypeDef(TypedDict):
    ACL: NotRequired[ObjectCannedACLType]
    Body: NotRequired[BlobTypeDef]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ContentType: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    WriteOffsetBytes: NotRequired[int]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    ACL: NotRequired[ObjectCannedACLType]
    Body: NotRequired[BlobTypeDef]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ContentType: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    WriteOffsetBytes: NotRequired[int]
    Metadata: NotRequired[Mapping[str, str]]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]


class UploadPartRequestMultipartUploadPartUploadTypeDef(TypedDict):
    Body: NotRequired[BlobTypeDef]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class UploadPartRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    PartNumber: int
    UploadId: str
    Body: NotRequired[BlobTypeDef]
    ContentLength: NotRequired[int]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]


class WriteGetObjectResponseRequestRequestTypeDef(TypedDict):
    RequestRoute: str
    RequestToken: str
    Body: NotRequired[BlobTypeDef]
    StatusCode: NotRequired[int]
    ErrorCode: NotRequired[str]
    ErrorMessage: NotRequired[str]
    AcceptRanges: NotRequired[str]
    CacheControl: NotRequired[str]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentLength: NotRequired[int]
    ContentRange: NotRequired[str]
    ContentType: NotRequired[str]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    DeleteMarker: NotRequired[bool]
    ETag: NotRequired[str]
    Expires: NotRequired[TimestampTypeDef]
    Expiration: NotRequired[str]
    LastModified: NotRequired[TimestampTypeDef]
    MissingMeta: NotRequired[int]
    Metadata: NotRequired[Mapping[str, str]]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    PartsCount: NotRequired[int]
    ReplicationStatus: NotRequired[ReplicationStatusType]
    RequestCharged: NotRequired[Literal["requester"]]
    Restore: NotRequired[str]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    SSECustomerAlgorithm: NotRequired[str]
    SSEKMSKeyId: NotRequired[str]
    StorageClass: NotRequired[StorageClassType]
    TagCount: NotRequired[int]
    VersionId: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]


class BucketCopyRequestTypeDef(TypedDict):
    CopySource: CopySourceTypeDef
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    SourceClient: NotRequired[BaseClient | None]
    Config: NotRequired[TransferConfig | None]


class ClientCopyRequestTypeDef(TypedDict):
    CopySource: CopySourceTypeDef
    Bucket: str
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    SourceClient: NotRequired[BaseClient | None]
    Config: NotRequired[TransferConfig | None]


CopySourceOrStrTypeDef = Union[str, CopySourceTypeDef]


class ObjectCopyRequestTypeDef(TypedDict):
    CopySource: CopySourceTypeDef
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    SourceClient: NotRequired[BaseClient | None]
    Config: NotRequired[TransferConfig | None]


class BucketDownloadFileobjRequestTypeDef(TypedDict):
    Key: str
    Fileobj: FileobjTypeDef
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class BucketUploadFileobjRequestTypeDef(TypedDict):
    Fileobj: FileobjTypeDef
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ClientDownloadFileobjRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Fileobj: FileobjTypeDef
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ClientUploadFileobjRequestTypeDef(TypedDict):
    Fileobj: FileobjTypeDef
    Bucket: str
    Key: str
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ObjectDownloadFileobjRequestTypeDef(TypedDict):
    Fileobj: FileobjTypeDef
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ObjectUploadFileobjRequestTypeDef(TypedDict):
    Fileobj: FileobjTypeDef
    ExtraArgs: NotRequired[Dict[str, Any] | None]
    Callback: NotRequired[Callable[..., Any] | None]
    Config: NotRequired[TransferConfig | None]


class ListBucketsOutputTypeDef(TypedDict):
    Buckets: List[BucketTypeDef]
    Owner: OwnerTypeDef
    ContinuationToken: str
    Prefix: str
    ResponseMetadata: ResponseMetadataTypeDef


class ListDirectoryBucketsOutputTypeDef(TypedDict):
    Buckets: List[BucketTypeDef]
    ContinuationToken: str
    ResponseMetadata: ResponseMetadataTypeDef


class CORSConfigurationTypeDef(TypedDict):
    CORSRules: Sequence[CORSRuleTypeDef]


class GetBucketCorsOutputTypeDef(TypedDict):
    CORSRules: List[CORSRuleOutputTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


CloudFunctionConfigurationUnionTypeDef = Union[
    CloudFunctionConfigurationTypeDef, CloudFunctionConfigurationOutputTypeDef
]


class CompletedMultipartUploadTypeDef(TypedDict):
    Parts: NotRequired[Sequence[CompletedPartTypeDef]]


class CopyObjectOutputTypeDef(TypedDict):
    CopyObjectResult: CopyObjectResultTypeDef
    Expiration: str
    CopySourceVersionId: str
    VersionId: str
    ServerSideEncryption: ServerSideEncryptionType
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    SSEKMSEncryptionContext: str
    BucketKeyEnabled: bool
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class UploadPartCopyOutputTypeDef(TypedDict):
    CopySourceVersionId: str
    CopyPartResult: CopyPartResultTypeDef
    ServerSideEncryption: ServerSideEncryptionType
    SSECustomerAlgorithm: str
    SSECustomerKeyMD5: str
    SSEKMSKeyId: str
    BucketKeyEnabled: bool
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class CreateBucketConfigurationTypeDef(TypedDict):
    LocationConstraint: NotRequired[BucketLocationConstraintType]
    Location: NotRequired[LocationInfoTypeDef]
    Bucket: NotRequired[BucketInfoTypeDef]


class CreateSessionOutputTypeDef(TypedDict):
    ServerSideEncryption: ServerSideEncryptionType
    SSEKMSKeyId: str
    SSEKMSEncryptionContext: str
    BucketKeyEnabled: bool
    Credentials: SessionCredentialsTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ObjectLockRuleTypeDef(TypedDict):
    DefaultRetention: NotRequired[DefaultRetentionTypeDef]


class DeleteObjectsOutputTypeDef(TypedDict):
    Deleted: List[DeletedObjectTypeDef]
    RequestCharged: Literal["requester"]
    Errors: List[ErrorTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class S3KeyFilterOutputTypeDef(TypedDict):
    FilterRules: NotRequired[List[FilterRuleTypeDef]]


class S3KeyFilterTypeDef(TypedDict):
    FilterRules: NotRequired[Sequence[FilterRuleTypeDef]]


class GetBucketPolicyStatusOutputTypeDef(TypedDict):
    PolicyStatus: PolicyStatusTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class GetObjectAttributesPartsTypeDef(TypedDict):
    TotalPartsCount: NotRequired[int]
    PartNumberMarker: NotRequired[int]
    NextPartNumberMarker: NotRequired[int]
    MaxParts: NotRequired[int]
    IsTruncated: NotRequired[bool]
    Parts: NotRequired[List[ObjectPartTypeDef]]


class GetObjectLegalHoldOutputTypeDef(TypedDict):
    LegalHold: ObjectLockLegalHoldTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectLegalHoldRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    LegalHold: NotRequired[ObjectLockLegalHoldTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    VersionId: NotRequired[str]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class GetObjectRetentionOutputTypeDef(TypedDict):
    Retention: ObjectLockRetentionOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class GetPublicAccessBlockOutputTypeDef(TypedDict):
    PublicAccessBlockConfiguration: PublicAccessBlockConfigurationTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutPublicAccessBlockRequestRequestTypeDef(TypedDict):
    Bucket: str
    PublicAccessBlockConfiguration: PublicAccessBlockConfigurationTypeDef
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class GrantTypeDef(TypedDict):
    Grantee: NotRequired[GranteeTypeDef]
    Permission: NotRequired[PermissionType]


class TargetGrantTypeDef(TypedDict):
    Grantee: NotRequired[GranteeTypeDef]
    Permission: NotRequired[BucketLogsPermissionType]


class HeadBucketRequestWaitTypeDef(TypedDict):
    Bucket: str
    ExpectedBucketOwner: NotRequired[str]
    WaiterConfig: NotRequired[WaiterConfigTypeDef]


class HeadObjectRequestWaitTypeDef(TypedDict):
    Bucket: str
    Key: str
    IfMatch: NotRequired[str]
    IfModifiedSince: NotRequired[TimestampTypeDef]
    IfNoneMatch: NotRequired[str]
    IfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Range: NotRequired[str]
    ResponseCacheControl: NotRequired[str]
    ResponseContentDisposition: NotRequired[str]
    ResponseContentEncoding: NotRequired[str]
    ResponseContentLanguage: NotRequired[str]
    ResponseContentType: NotRequired[str]
    ResponseExpires: NotRequired[TimestampTypeDef]
    VersionId: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    PartNumber: NotRequired[int]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumMode: NotRequired[Literal["ENABLED"]]
    WaiterConfig: NotRequired[WaiterConfigTypeDef]


class MultipartUploadTypeDef(TypedDict):
    UploadId: NotRequired[str]
    Key: NotRequired[str]
    Initiated: NotRequired[datetime]
    StorageClass: NotRequired[StorageClassType]
    Owner: NotRequired[OwnerTypeDef]
    Initiator: NotRequired[InitiatorTypeDef]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class InputSerializationTypeDef(TypedDict):
    CSV: NotRequired[CSVInputTypeDef]
    CompressionType: NotRequired[CompressionTypeType]
    JSON: NotRequired[JSONInputTypeDef]
    Parquet: NotRequired[Mapping[str, Any]]


class InventoryEncryptionOutputTypeDef(TypedDict):
    SSES3: NotRequired[Dict[str, Any]]
    SSEKMS: NotRequired[SSEKMSTypeDef]


class InventoryEncryptionTypeDef(TypedDict):
    SSES3: NotRequired[Mapping[str, Any]]
    SSEKMS: NotRequired[SSEKMSTypeDef]


class OutputSerializationTypeDef(TypedDict):
    CSV: NotRequired[CSVOutputTypeDef]
    JSON: NotRequired[JSONOutputTypeDef]


class RuleOutputTypeDef(TypedDict):
    Prefix: str
    Status: ExpirationStatusType
    Expiration: NotRequired[LifecycleExpirationOutputTypeDef]
    ID: NotRequired[str]
    Transition: NotRequired[TransitionOutputTypeDef]
    NoncurrentVersionTransition: NotRequired[NoncurrentVersionTransitionTypeDef]
    NoncurrentVersionExpiration: NotRequired[NoncurrentVersionExpirationTypeDef]
    AbortIncompleteMultipartUpload: NotRequired[AbortIncompleteMultipartUploadTypeDef]


class ListBucketsRequestPaginateTypeDef(TypedDict):
    Prefix: NotRequired[str]
    BucketRegion: NotRequired[str]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListDirectoryBucketsRequestPaginateTypeDef(TypedDict):
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListMultipartUploadsRequestPaginateTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    Prefix: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListObjectVersionsRequestPaginateTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    Prefix: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListObjectsRequestPaginateTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    Prefix: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListObjectsV2RequestPaginateTypeDef(TypedDict):
    Bucket: str
    Delimiter: NotRequired[str]
    EncodingType: NotRequired[Literal["url"]]
    Prefix: NotRequired[str]
    FetchOwner: NotRequired[bool]
    StartAfter: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    OptionalObjectAttributes: NotRequired[Sequence[Literal["RestoreStatus"]]]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListPartsRequestPaginateTypeDef(TypedDict):
    Bucket: str
    Key: str
    UploadId: str
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    PaginationConfig: NotRequired[PaginatorConfigTypeDef]


class ListPartsOutputTypeDef(TypedDict):
    AbortDate: datetime
    AbortRuleId: str
    Bucket: str
    Key: str
    UploadId: str
    PartNumberMarker: int
    NextPartNumberMarker: int
    MaxParts: int
    IsTruncated: bool
    Parts: List[PartTypeDef]
    Initiator: InitiatorTypeDef
    Owner: OwnerTypeDef
    StorageClass: StorageClassType
    RequestCharged: Literal["requester"]
    ChecksumAlgorithm: ChecksumAlgorithmType
    ResponseMetadata: ResponseMetadataTypeDef


class MetadataTableConfigurationResultTypeDef(TypedDict):
    S3TablesDestinationResult: S3TablesDestinationResultTypeDef


class MetadataTableConfigurationTypeDef(TypedDict):
    S3TablesDestination: S3TablesDestinationTypeDef


class MetricsTypeDef(TypedDict):
    Status: MetricsStatusType
    EventThreshold: NotRequired[ReplicationTimeValueTypeDef]


class ReplicationTimeTypeDef(TypedDict):
    Status: ReplicationTimeStatusType
    Time: ReplicationTimeValueTypeDef


class NotificationConfigurationDeprecatedResponseTypeDef(TypedDict):
    TopicConfiguration: TopicConfigurationDeprecatedOutputTypeDef
    QueueConfiguration: QueueConfigurationDeprecatedOutputTypeDef
    CloudFunctionConfiguration: CloudFunctionConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ObjectTypeDef(TypedDict):
    Key: NotRequired[str]
    LastModified: NotRequired[datetime]
    ETag: NotRequired[str]
    ChecksumAlgorithm: NotRequired[List[ChecksumAlgorithmType]]
    Size: NotRequired[int]
    StorageClass: NotRequired[ObjectStorageClassType]
    Owner: NotRequired[OwnerTypeDef]
    RestoreStatus: NotRequired[RestoreStatusTypeDef]


class ObjectVersionTypeDef(TypedDict):
    ETag: NotRequired[str]
    ChecksumAlgorithm: NotRequired[List[ChecksumAlgorithmType]]
    Size: NotRequired[int]
    StorageClass: NotRequired[Literal["STANDARD"]]
    Key: NotRequired[str]
    VersionId: NotRequired[str]
    IsLatest: NotRequired[bool]
    LastModified: NotRequired[datetime]
    Owner: NotRequired[OwnerTypeDef]
    RestoreStatus: NotRequired[RestoreStatusTypeDef]


class OwnershipControlsOutputTypeDef(TypedDict):
    Rules: List[OwnershipControlsRuleTypeDef]


class OwnershipControlsTypeDef(TypedDict):
    Rules: Sequence[OwnershipControlsRuleTypeDef]


class TargetObjectKeyFormatOutputTypeDef(TypedDict):
    SimplePrefix: NotRequired[Dict[str, Any]]
    PartitionedPrefix: NotRequired[PartitionedPrefixTypeDef]


class TargetObjectKeyFormatTypeDef(TypedDict):
    SimplePrefix: NotRequired[Mapping[str, Any]]
    PartitionedPrefix: NotRequired[PartitionedPrefixTypeDef]


class ProgressEventTypeDef(TypedDict):
    Details: NotRequired[ProgressTypeDef]


class PutBucketRequestPaymentRequestBucketRequestPaymentPutTypeDef(TypedDict):
    RequestPaymentConfiguration: RequestPaymentConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketRequestPaymentRequestRequestTypeDef(TypedDict):
    Bucket: str
    RequestPaymentConfiguration: RequestPaymentConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketVersioningRequestBucketVersioningPutTypeDef(TypedDict):
    VersioningConfiguration: VersioningConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    MFA: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketVersioningRequestRequestTypeDef(TypedDict):
    Bucket: str
    VersioningConfiguration: VersioningConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    MFA: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


QueueConfigurationDeprecatedUnionTypeDef = Union[
    QueueConfigurationDeprecatedTypeDef, QueueConfigurationDeprecatedOutputTypeDef
]


class RoutingRuleTypeDef(TypedDict):
    Redirect: RedirectTypeDef
    Condition: NotRequired[ConditionTypeDef]


class ServerSideEncryptionRuleTypeDef(TypedDict):
    ApplyServerSideEncryptionByDefault: NotRequired[ServerSideEncryptionByDefaultTypeDef]
    BucketKeyEnabled: NotRequired[bool]


class SourceSelectionCriteriaTypeDef(TypedDict):
    SseKmsEncryptedObjects: NotRequired[SseKmsEncryptedObjectsTypeDef]
    ReplicaModifications: NotRequired[ReplicaModificationsTypeDef]


class StatsEventTypeDef(TypedDict):
    Details: NotRequired[StatsTypeDef]


TopicConfigurationDeprecatedUnionTypeDef = Union[
    TopicConfigurationDeprecatedTypeDef, TopicConfigurationDeprecatedOutputTypeDef
]


class DeleteTypeDef(TypedDict):
    Objects: Sequence[ObjectIdentifierTypeDef]
    Quiet: NotRequired[bool]


class PutObjectRetentionRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Retention: NotRequired[ObjectLockRetentionTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    VersionId: NotRequired[str]
    BypassGovernanceRetention: NotRequired[bool]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class RuleTypeDef(TypedDict):
    Prefix: str
    Status: ExpirationStatusType
    Expiration: NotRequired[LifecycleExpirationTypeDef]
    ID: NotRequired[str]
    Transition: NotRequired[TransitionTypeDef]
    NoncurrentVersionTransition: NotRequired[NoncurrentVersionTransitionTypeDef]
    NoncurrentVersionExpiration: NotRequired[NoncurrentVersionExpirationTypeDef]
    AbortIncompleteMultipartUpload: NotRequired[AbortIncompleteMultipartUploadTypeDef]


class AnalyticsFilterOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[AnalyticsAndOperatorOutputTypeDef]


AnalyticsAndOperatorUnionTypeDef = Union[
    AnalyticsAndOperatorTypeDef, AnalyticsAndOperatorOutputTypeDef
]


class IntelligentTieringFilterOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[IntelligentTieringAndOperatorOutputTypeDef]


IntelligentTieringAndOperatorUnionTypeDef = Union[
    IntelligentTieringAndOperatorTypeDef, IntelligentTieringAndOperatorOutputTypeDef
]


class LifecycleRuleFilterOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    ObjectSizeGreaterThan: NotRequired[int]
    ObjectSizeLessThan: NotRequired[int]
    And: NotRequired[LifecycleRuleAndOperatorOutputTypeDef]


class LifecycleRuleFilterTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    ObjectSizeGreaterThan: NotRequired[int]
    ObjectSizeLessThan: NotRequired[int]
    And: NotRequired[LifecycleRuleAndOperatorTypeDef]


class MetricsFilterOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    AccessPointArn: NotRequired[str]
    And: NotRequired[MetricsAndOperatorOutputTypeDef]


MetricsAndOperatorUnionTypeDef = Union[MetricsAndOperatorTypeDef, MetricsAndOperatorOutputTypeDef]


class ReplicationRuleFilterOutputTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[ReplicationRuleAndOperatorOutputTypeDef]


ReplicationRuleAndOperatorUnionTypeDef = Union[
    ReplicationRuleAndOperatorTypeDef, ReplicationRuleAndOperatorOutputTypeDef
]


class PutBucketTaggingRequestBucketTaggingPutTypeDef(TypedDict):
    Tagging: TaggingTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    Tagging: TaggingTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectTaggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Tagging: TaggingTypeDef
    VersionId: NotRequired[str]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]


class StorageClassAnalysisDataExportTypeDef(TypedDict):
    OutputSchemaVersion: Literal["V_1"]
    Destination: AnalyticsExportDestinationTypeDef


class CopyObjectRequestObjectCopyFromTypeDef(TypedDict):
    CopySource: CopySourceOrStrTypeDef
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    CopySourceIfMatch: NotRequired[str]
    CopySourceIfModifiedSince: NotRequired[TimestampTypeDef]
    CopySourceIfNoneMatch: NotRequired[str]
    CopySourceIfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    MetadataDirective: NotRequired[MetadataDirectiveType]
    TaggingDirective: NotRequired[TaggingDirectiveType]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    CopySourceSSECustomerAlgorithm: NotRequired[str]
    CopySourceSSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ExpectedSourceBucketOwner: NotRequired[str]


class CopyObjectRequestObjectSummaryCopyFromTypeDef(TypedDict):
    CopySource: CopySourceOrStrTypeDef
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    CopySourceIfMatch: NotRequired[str]
    CopySourceIfModifiedSince: NotRequired[TimestampTypeDef]
    CopySourceIfNoneMatch: NotRequired[str]
    CopySourceIfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    MetadataDirective: NotRequired[MetadataDirectiveType]
    TaggingDirective: NotRequired[TaggingDirectiveType]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    CopySourceSSECustomerAlgorithm: NotRequired[str]
    CopySourceSSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ExpectedSourceBucketOwner: NotRequired[str]


class CopyObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    CopySource: CopySourceOrStrTypeDef
    Key: str
    ACL: NotRequired[ObjectCannedACLType]
    CacheControl: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ContentDisposition: NotRequired[str]
    ContentEncoding: NotRequired[str]
    ContentLanguage: NotRequired[str]
    ContentType: NotRequired[str]
    CopySourceIfMatch: NotRequired[str]
    CopySourceIfModifiedSince: NotRequired[TimestampTypeDef]
    CopySourceIfNoneMatch: NotRequired[str]
    CopySourceIfUnmodifiedSince: NotRequired[TimestampTypeDef]
    Expires: NotRequired[TimestampTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    Metadata: NotRequired[Mapping[str, str]]
    MetadataDirective: NotRequired[MetadataDirectiveType]
    TaggingDirective: NotRequired[TaggingDirectiveType]
    ServerSideEncryption: NotRequired[ServerSideEncryptionType]
    StorageClass: NotRequired[StorageClassType]
    WebsiteRedirectLocation: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    SSEKMSKeyId: NotRequired[str]
    SSEKMSEncryptionContext: NotRequired[str]
    BucketKeyEnabled: NotRequired[bool]
    CopySourceSSECustomerAlgorithm: NotRequired[str]
    CopySourceSSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    Tagging: NotRequired[str]
    ObjectLockMode: NotRequired[ObjectLockModeType]
    ObjectLockRetainUntilDate: NotRequired[TimestampTypeDef]
    ObjectLockLegalHoldStatus: NotRequired[ObjectLockLegalHoldStatusType]
    ExpectedBucketOwner: NotRequired[str]
    ExpectedSourceBucketOwner: NotRequired[str]


class UploadPartCopyRequestMultipartUploadPartCopyFromTypeDef(TypedDict):
    CopySource: CopySourceOrStrTypeDef
    CopySourceIfMatch: NotRequired[str]
    CopySourceIfModifiedSince: NotRequired[TimestampTypeDef]
    CopySourceIfNoneMatch: NotRequired[str]
    CopySourceIfUnmodifiedSince: NotRequired[TimestampTypeDef]
    CopySourceRange: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    CopySourceSSECustomerAlgorithm: NotRequired[str]
    CopySourceSSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    ExpectedSourceBucketOwner: NotRequired[str]


class UploadPartCopyRequestRequestTypeDef(TypedDict):
    Bucket: str
    CopySource: CopySourceOrStrTypeDef
    Key: str
    PartNumber: int
    UploadId: str
    CopySourceIfMatch: NotRequired[str]
    CopySourceIfModifiedSince: NotRequired[TimestampTypeDef]
    CopySourceIfNoneMatch: NotRequired[str]
    CopySourceIfUnmodifiedSince: NotRequired[TimestampTypeDef]
    CopySourceRange: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    CopySourceSSECustomerAlgorithm: NotRequired[str]
    CopySourceSSECustomerKey: NotRequired[str | bytes]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    ExpectedSourceBucketOwner: NotRequired[str]


class PutBucketCorsRequestBucketCorsPutTypeDef(TypedDict):
    CORSConfiguration: CORSConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketCorsRequestRequestTypeDef(TypedDict):
    Bucket: str
    CORSConfiguration: CORSConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class CompleteMultipartUploadRequestMultipartUploadCompleteTypeDef(TypedDict):
    MultipartUpload: NotRequired[CompletedMultipartUploadTypeDef]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]


class CompleteMultipartUploadRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    UploadId: str
    MultipartUpload: NotRequired[CompletedMultipartUploadTypeDef]
    ChecksumCRC32: NotRequired[str]
    ChecksumCRC32C: NotRequired[str]
    ChecksumSHA1: NotRequired[str]
    ChecksumSHA256: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    ExpectedBucketOwner: NotRequired[str]
    IfMatch: NotRequired[str]
    IfNoneMatch: NotRequired[str]
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]


class CreateBucketRequestBucketCreateTypeDef(TypedDict):
    ACL: NotRequired[BucketCannedACLType]
    CreateBucketConfiguration: NotRequired[CreateBucketConfigurationTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    ObjectLockEnabledForBucket: NotRequired[bool]
    ObjectOwnership: NotRequired[ObjectOwnershipType]


class CreateBucketRequestRequestTypeDef(TypedDict):
    Bucket: str
    ACL: NotRequired[BucketCannedACLType]
    CreateBucketConfiguration: NotRequired[CreateBucketConfigurationTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    ObjectLockEnabledForBucket: NotRequired[bool]
    ObjectOwnership: NotRequired[ObjectOwnershipType]


class CreateBucketRequestServiceResourceCreateBucketTypeDef(TypedDict):
    Bucket: str
    ACL: NotRequired[BucketCannedACLType]
    CreateBucketConfiguration: NotRequired[CreateBucketConfigurationTypeDef]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    ObjectLockEnabledForBucket: NotRequired[bool]
    ObjectOwnership: NotRequired[ObjectOwnershipType]


class ObjectLockConfigurationTypeDef(TypedDict):
    ObjectLockEnabled: NotRequired[Literal["Enabled"]]
    Rule: NotRequired[ObjectLockRuleTypeDef]


class NotificationConfigurationFilterOutputTypeDef(TypedDict):
    Key: NotRequired[S3KeyFilterOutputTypeDef]


class NotificationConfigurationFilterTypeDef(TypedDict):
    Key: NotRequired[S3KeyFilterTypeDef]


class GetObjectAttributesOutputTypeDef(TypedDict):
    DeleteMarker: bool
    LastModified: datetime
    VersionId: str
    RequestCharged: Literal["requester"]
    ETag: str
    Checksum: ChecksumTypeDef
    ObjectParts: GetObjectAttributesPartsTypeDef
    StorageClass: StorageClassType
    ObjectSize: int
    ResponseMetadata: ResponseMetadataTypeDef


class AccessControlPolicyTypeDef(TypedDict):
    Grants: NotRequired[Sequence[GrantTypeDef]]
    Owner: NotRequired[OwnerTypeDef]


class GetBucketAclOutputTypeDef(TypedDict):
    Owner: OwnerTypeDef
    Grants: List[GrantTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class GetObjectAclOutputTypeDef(TypedDict):
    Owner: OwnerTypeDef
    Grants: List[GrantTypeDef]
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef


class S3LocationTypeDef(TypedDict):
    BucketName: str
    Prefix: str
    Encryption: NotRequired[EncryptionTypeDef]
    CannedACL: NotRequired[ObjectCannedACLType]
    AccessControlList: NotRequired[Sequence[GrantTypeDef]]
    Tagging: NotRequired[TaggingTypeDef]
    UserMetadata: NotRequired[Sequence[MetadataEntryTypeDef]]
    StorageClass: NotRequired[StorageClassType]


class ListMultipartUploadsOutputTypeDef(TypedDict):
    Bucket: str
    KeyMarker: str
    UploadIdMarker: str
    NextKeyMarker: str
    Prefix: str
    Delimiter: str
    NextUploadIdMarker: str
    MaxUploads: int
    IsTruncated: bool
    Uploads: List[MultipartUploadTypeDef]
    EncodingType: Literal["url"]
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef
    CommonPrefixes: NotRequired[List[CommonPrefixTypeDef]]


class InventoryS3BucketDestinationOutputTypeDef(TypedDict):
    Bucket: str
    Format: InventoryFormatType
    AccountId: NotRequired[str]
    Prefix: NotRequired[str]
    Encryption: NotRequired[InventoryEncryptionOutputTypeDef]


InventoryEncryptionUnionTypeDef = Union[
    InventoryEncryptionTypeDef, InventoryEncryptionOutputTypeDef
]


class SelectObjectContentRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    Expression: str
    ExpressionType: Literal["SQL"]
    InputSerialization: InputSerializationTypeDef
    OutputSerialization: OutputSerializationTypeDef
    SSECustomerAlgorithm: NotRequired[str]
    SSECustomerKey: NotRequired[str | bytes]
    RequestProgress: NotRequired[RequestProgressTypeDef]
    ScanRange: NotRequired[ScanRangeTypeDef]
    ExpectedBucketOwner: NotRequired[str]


class SelectParametersTypeDef(TypedDict):
    InputSerialization: InputSerializationTypeDef
    ExpressionType: Literal["SQL"]
    Expression: str
    OutputSerialization: OutputSerializationTypeDef


class GetBucketLifecycleOutputTypeDef(TypedDict):
    Rules: List[RuleOutputTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class GetBucketMetadataTableConfigurationResultTypeDef(TypedDict):
    MetadataTableConfigurationResult: MetadataTableConfigurationResultTypeDef
    Status: str
    Error: NotRequired[ErrorDetailsTypeDef]


class CreateBucketMetadataTableConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    MetadataTableConfiguration: MetadataTableConfigurationTypeDef
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class DestinationTypeDef(TypedDict):
    Bucket: str
    Account: NotRequired[str]
    StorageClass: NotRequired[StorageClassType]
    AccessControlTranslation: NotRequired[AccessControlTranslationTypeDef]
    EncryptionConfiguration: NotRequired[EncryptionConfigurationTypeDef]
    ReplicationTime: NotRequired[ReplicationTimeTypeDef]
    Metrics: NotRequired[MetricsTypeDef]


class ListObjectsOutputTypeDef(TypedDict):
    IsTruncated: bool
    Marker: str
    NextMarker: str
    Name: str
    Prefix: str
    Delimiter: str
    MaxKeys: int
    EncodingType: Literal["url"]
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef
    Contents: NotRequired[List[ObjectTypeDef]]
    CommonPrefixes: NotRequired[List[CommonPrefixTypeDef]]


class ListObjectsV2OutputTypeDef(TypedDict):
    IsTruncated: bool
    Name: str
    Prefix: str
    Delimiter: str
    MaxKeys: int
    EncodingType: Literal["url"]
    KeyCount: int
    ContinuationToken: str
    NextContinuationToken: str
    StartAfter: str
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef
    Contents: NotRequired[List[ObjectTypeDef]]
    CommonPrefixes: NotRequired[List[CommonPrefixTypeDef]]


class ListObjectVersionsOutputTypeDef(TypedDict):
    IsTruncated: bool
    KeyMarker: str
    VersionIdMarker: str
    NextKeyMarker: str
    NextVersionIdMarker: str
    Versions: List[ObjectVersionTypeDef]
    DeleteMarkers: List[DeleteMarkerEntryTypeDef]
    Name: str
    Prefix: str
    Delimiter: str
    MaxKeys: int
    EncodingType: Literal["url"]
    RequestCharged: Literal["requester"]
    ResponseMetadata: ResponseMetadataTypeDef
    CommonPrefixes: NotRequired[List[CommonPrefixTypeDef]]


class GetBucketOwnershipControlsOutputTypeDef(TypedDict):
    OwnershipControls: OwnershipControlsOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketOwnershipControlsRequestRequestTypeDef(TypedDict):
    Bucket: str
    OwnershipControls: OwnershipControlsTypeDef
    ContentMD5: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class LoggingEnabledOutputTypeDef(TypedDict):
    TargetBucket: str
    TargetPrefix: str
    TargetGrants: NotRequired[List[TargetGrantTypeDef]]
    TargetObjectKeyFormat: NotRequired[TargetObjectKeyFormatOutputTypeDef]


class LoggingEnabledTypeDef(TypedDict):
    TargetBucket: str
    TargetPrefix: str
    TargetGrants: NotRequired[Sequence[TargetGrantTypeDef]]
    TargetObjectKeyFormat: NotRequired[TargetObjectKeyFormatTypeDef]


class GetBucketWebsiteOutputTypeDef(TypedDict):
    RedirectAllRequestsTo: RedirectAllRequestsToTypeDef
    IndexDocument: IndexDocumentTypeDef
    ErrorDocument: ErrorDocumentTypeDef
    RoutingRules: List[RoutingRuleTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class WebsiteConfigurationTypeDef(TypedDict):
    ErrorDocument: NotRequired[ErrorDocumentTypeDef]
    IndexDocument: NotRequired[IndexDocumentTypeDef]
    RedirectAllRequestsTo: NotRequired[RedirectAllRequestsToTypeDef]
    RoutingRules: NotRequired[Sequence[RoutingRuleTypeDef]]


class ServerSideEncryptionConfigurationOutputTypeDef(TypedDict):
    Rules: List[ServerSideEncryptionRuleTypeDef]


class ServerSideEncryptionConfigurationTypeDef(TypedDict):
    Rules: Sequence[ServerSideEncryptionRuleTypeDef]


class SelectObjectContentEventStreamTypeDef(TypedDict):
    Records: NotRequired[RecordsEventTypeDef]
    Stats: NotRequired[StatsEventTypeDef]
    Progress: NotRequired[ProgressEventTypeDef]
    Cont: NotRequired[Dict[str, Any]]
    End: NotRequired[Dict[str, Any]]


class NotificationConfigurationDeprecatedTypeDef(TypedDict):
    TopicConfiguration: NotRequired[TopicConfigurationDeprecatedUnionTypeDef]
    QueueConfiguration: NotRequired[QueueConfigurationDeprecatedUnionTypeDef]
    CloudFunctionConfiguration: NotRequired[CloudFunctionConfigurationUnionTypeDef]


class DeleteObjectsRequestBucketDeleteObjectsTypeDef(TypedDict):
    Delete: DeleteTypeDef
    MFA: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class DeleteObjectsRequestRequestTypeDef(TypedDict):
    Bucket: str
    Delete: DeleteTypeDef
    MFA: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    BypassGovernanceRetention: NotRequired[bool]
    ExpectedBucketOwner: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]


class LifecycleConfigurationTypeDef(TypedDict):
    Rules: Sequence[RuleTypeDef]


class AnalyticsFilterTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[AnalyticsAndOperatorUnionTypeDef]


class IntelligentTieringConfigurationOutputTypeDef(TypedDict):
    Id: str
    Status: IntelligentTieringStatusType
    Tierings: List[TieringTypeDef]
    Filter: NotRequired[IntelligentTieringFilterOutputTypeDef]


class IntelligentTieringFilterTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[IntelligentTieringAndOperatorUnionTypeDef]


class LifecycleRuleOutputTypeDef(TypedDict):
    Status: ExpirationStatusType
    Expiration: NotRequired[LifecycleExpirationOutputTypeDef]
    ID: NotRequired[str]
    Prefix: NotRequired[str]
    Filter: NotRequired[LifecycleRuleFilterOutputTypeDef]
    Transitions: NotRequired[List[TransitionOutputTypeDef]]
    NoncurrentVersionTransitions: NotRequired[List[NoncurrentVersionTransitionTypeDef]]
    NoncurrentVersionExpiration: NotRequired[NoncurrentVersionExpirationTypeDef]
    AbortIncompleteMultipartUpload: NotRequired[AbortIncompleteMultipartUploadTypeDef]


class LifecycleRuleTypeDef(TypedDict):
    Status: ExpirationStatusType
    Expiration: NotRequired[LifecycleExpirationTypeDef]
    ID: NotRequired[str]
    Prefix: NotRequired[str]
    Filter: NotRequired[LifecycleRuleFilterTypeDef]
    Transitions: NotRequired[Sequence[TransitionTypeDef]]
    NoncurrentVersionTransitions: NotRequired[Sequence[NoncurrentVersionTransitionTypeDef]]
    NoncurrentVersionExpiration: NotRequired[NoncurrentVersionExpirationTypeDef]
    AbortIncompleteMultipartUpload: NotRequired[AbortIncompleteMultipartUploadTypeDef]


class MetricsConfigurationOutputTypeDef(TypedDict):
    Id: str
    Filter: NotRequired[MetricsFilterOutputTypeDef]


class MetricsFilterTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    AccessPointArn: NotRequired[str]
    And: NotRequired[MetricsAndOperatorUnionTypeDef]


class ReplicationRuleFilterTypeDef(TypedDict):
    Prefix: NotRequired[str]
    Tag: NotRequired[TagTypeDef]
    And: NotRequired[ReplicationRuleAndOperatorUnionTypeDef]


class StorageClassAnalysisTypeDef(TypedDict):
    DataExport: NotRequired[StorageClassAnalysisDataExportTypeDef]


class GetObjectLockConfigurationOutputTypeDef(TypedDict):
    ObjectLockConfiguration: ObjectLockConfigurationTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutObjectLockConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ObjectLockConfiguration: NotRequired[ObjectLockConfigurationTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    Token: NotRequired[str]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class LambdaFunctionConfigurationOutputTypeDef(TypedDict):
    LambdaFunctionArn: str
    Events: List[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterOutputTypeDef]


class QueueConfigurationOutputTypeDef(TypedDict):
    QueueArn: str
    Events: List[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterOutputTypeDef]


class TopicConfigurationOutputTypeDef(TypedDict):
    TopicArn: str
    Events: List[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterOutputTypeDef]


class LambdaFunctionConfigurationTypeDef(TypedDict):
    LambdaFunctionArn: str
    Events: Sequence[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterTypeDef]


class QueueConfigurationTypeDef(TypedDict):
    QueueArn: str
    Events: Sequence[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterTypeDef]


class TopicConfigurationTypeDef(TypedDict):
    TopicArn: str
    Events: Sequence[EventType]
    Id: NotRequired[str]
    Filter: NotRequired[NotificationConfigurationFilterTypeDef]


class PutBucketAclRequestBucketAclPutTypeDef(TypedDict):
    ACL: NotRequired[BucketCannedACLType]
    AccessControlPolicy: NotRequired[AccessControlPolicyTypeDef]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketAclRequestRequestTypeDef(TypedDict):
    Bucket: str
    ACL: NotRequired[BucketCannedACLType]
    AccessControlPolicy: NotRequired[AccessControlPolicyTypeDef]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectAclRequestObjectAclPutTypeDef(TypedDict):
    ACL: NotRequired[ObjectCannedACLType]
    AccessControlPolicy: NotRequired[AccessControlPolicyTypeDef]
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    VersionId: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PutObjectAclRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    ACL: NotRequired[ObjectCannedACLType]
    AccessControlPolicy: NotRequired[AccessControlPolicyTypeDef]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    GrantFullControl: NotRequired[str]
    GrantRead: NotRequired[str]
    GrantReadACP: NotRequired[str]
    GrantWrite: NotRequired[str]
    GrantWriteACP: NotRequired[str]
    RequestPayer: NotRequired[Literal["requester"]]
    VersionId: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class OutputLocationTypeDef(TypedDict):
    S3: NotRequired[S3LocationTypeDef]


class InventoryDestinationOutputTypeDef(TypedDict):
    S3BucketDestination: InventoryS3BucketDestinationOutputTypeDef


class InventoryS3BucketDestinationTypeDef(TypedDict):
    Bucket: str
    Format: InventoryFormatType
    AccountId: NotRequired[str]
    Prefix: NotRequired[str]
    Encryption: NotRequired[InventoryEncryptionUnionTypeDef]


class GetBucketMetadataTableConfigurationOutputTypeDef(TypedDict):
    GetBucketMetadataTableConfigurationResult: GetBucketMetadataTableConfigurationResultTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ReplicationRuleOutputTypeDef(TypedDict):
    Status: ReplicationRuleStatusType
    Destination: DestinationTypeDef
    ID: NotRequired[str]
    Priority: NotRequired[int]
    Prefix: NotRequired[str]
    Filter: NotRequired[ReplicationRuleFilterOutputTypeDef]
    SourceSelectionCriteria: NotRequired[SourceSelectionCriteriaTypeDef]
    ExistingObjectReplication: NotRequired[ExistingObjectReplicationTypeDef]
    DeleteMarkerReplication: NotRequired[DeleteMarkerReplicationTypeDef]


class GetBucketLoggingOutputTypeDef(TypedDict):
    LoggingEnabled: LoggingEnabledOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class BucketLoggingStatusTypeDef(TypedDict):
    LoggingEnabled: NotRequired[LoggingEnabledTypeDef]


class PutBucketWebsiteRequestBucketWebsitePutTypeDef(TypedDict):
    WebsiteConfiguration: WebsiteConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketWebsiteRequestRequestTypeDef(TypedDict):
    Bucket: str
    WebsiteConfiguration: WebsiteConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class GetBucketEncryptionOutputTypeDef(TypedDict):
    ServerSideEncryptionConfiguration: ServerSideEncryptionConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketEncryptionRequestRequestTypeDef(TypedDict):
    Bucket: str
    ServerSideEncryptionConfiguration: ServerSideEncryptionConfigurationTypeDef
    ContentMD5: NotRequired[str]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class SelectObjectContentOutputTypeDef(TypedDict):
    Payload: EventStream[SelectObjectContentEventStreamTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketNotificationRequestRequestTypeDef(TypedDict):
    Bucket: str
    NotificationConfiguration: NotificationConfigurationDeprecatedTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketLifecycleRequestBucketLifecyclePutTypeDef(TypedDict):
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    LifecycleConfiguration: NotRequired[LifecycleConfigurationTypeDef]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketLifecycleRequestRequestTypeDef(TypedDict):
    Bucket: str
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    LifecycleConfiguration: NotRequired[LifecycleConfigurationTypeDef]
    ExpectedBucketOwner: NotRequired[str]


AnalyticsFilterUnionTypeDef = Union[AnalyticsFilterTypeDef, AnalyticsFilterOutputTypeDef]


class GetBucketIntelligentTieringConfigurationOutputTypeDef(TypedDict):
    IntelligentTieringConfiguration: IntelligentTieringConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ListBucketIntelligentTieringConfigurationsOutputTypeDef(TypedDict):
    IsTruncated: bool
    ContinuationToken: str
    NextContinuationToken: str
    IntelligentTieringConfigurationList: List[IntelligentTieringConfigurationOutputTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


IntelligentTieringFilterUnionTypeDef = Union[
    IntelligentTieringFilterTypeDef, IntelligentTieringFilterOutputTypeDef
]


class GetBucketLifecycleConfigurationOutputTypeDef(TypedDict):
    Rules: List[LifecycleRuleOutputTypeDef]
    TransitionDefaultMinimumObjectSize: TransitionDefaultMinimumObjectSizeType
    ResponseMetadata: ResponseMetadataTypeDef


class BucketLifecycleConfigurationTypeDef(TypedDict):
    Rules: Sequence[LifecycleRuleTypeDef]


class GetBucketMetricsConfigurationOutputTypeDef(TypedDict):
    MetricsConfiguration: MetricsConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ListBucketMetricsConfigurationsOutputTypeDef(TypedDict):
    IsTruncated: bool
    ContinuationToken: str
    NextContinuationToken: str
    MetricsConfigurationList: List[MetricsConfigurationOutputTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


MetricsFilterUnionTypeDef = Union[MetricsFilterTypeDef, MetricsFilterOutputTypeDef]
ReplicationRuleFilterUnionTypeDef = Union[
    ReplicationRuleFilterTypeDef, ReplicationRuleFilterOutputTypeDef
]


class AnalyticsConfigurationOutputTypeDef(TypedDict):
    Id: str
    StorageClassAnalysis: StorageClassAnalysisTypeDef
    Filter: NotRequired[AnalyticsFilterOutputTypeDef]


class NotificationConfigurationResponseTypeDef(TypedDict):
    TopicConfigurations: List[TopicConfigurationOutputTypeDef]
    QueueConfigurations: List[QueueConfigurationOutputTypeDef]
    LambdaFunctionConfigurations: List[LambdaFunctionConfigurationOutputTypeDef]
    EventBridgeConfiguration: Dict[str, Any]
    ResponseMetadata: ResponseMetadataTypeDef


class NotificationConfigurationTypeDef(TypedDict):
    TopicConfigurations: NotRequired[Sequence[TopicConfigurationTypeDef]]
    QueueConfigurations: NotRequired[Sequence[QueueConfigurationTypeDef]]
    LambdaFunctionConfigurations: NotRequired[Sequence[LambdaFunctionConfigurationTypeDef]]
    EventBridgeConfiguration: NotRequired[Mapping[str, Any]]


RestoreRequestTypeDef = TypedDict(
    "RestoreRequestTypeDef",
    {
        "Days": NotRequired[int],
        "GlacierJobParameters": NotRequired[GlacierJobParametersTypeDef],
        "Type": NotRequired[Literal["SELECT"]],
        "Tier": NotRequired[TierType],
        "Description": NotRequired[str],
        "SelectParameters": NotRequired[SelectParametersTypeDef],
        "OutputLocation": NotRequired[OutputLocationTypeDef],
    },
)


class InventoryConfigurationOutputTypeDef(TypedDict):
    Destination: InventoryDestinationOutputTypeDef
    IsEnabled: bool
    Id: str
    IncludedObjectVersions: InventoryIncludedObjectVersionsType
    Schedule: InventoryScheduleTypeDef
    Filter: NotRequired[InventoryFilterTypeDef]
    OptionalFields: NotRequired[List[InventoryOptionalFieldType]]


InventoryS3BucketDestinationUnionTypeDef = Union[
    InventoryS3BucketDestinationTypeDef, InventoryS3BucketDestinationOutputTypeDef
]


class ReplicationConfigurationOutputTypeDef(TypedDict):
    Role: str
    Rules: List[ReplicationRuleOutputTypeDef]


class PutBucketLoggingRequestBucketLoggingPutTypeDef(TypedDict):
    BucketLoggingStatus: BucketLoggingStatusTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketLoggingRequestRequestTypeDef(TypedDict):
    Bucket: str
    BucketLoggingStatus: BucketLoggingStatusTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class AnalyticsConfigurationTypeDef(TypedDict):
    Id: str
    StorageClassAnalysis: StorageClassAnalysisTypeDef
    Filter: NotRequired[AnalyticsFilterUnionTypeDef]


class IntelligentTieringConfigurationTypeDef(TypedDict):
    Id: str
    Status: IntelligentTieringStatusType
    Tierings: Sequence[TieringTypeDef]
    Filter: NotRequired[IntelligentTieringFilterUnionTypeDef]


class PutBucketLifecycleConfigurationRequestBucketLifecycleConfigurationPutTypeDef(TypedDict):
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    LifecycleConfiguration: NotRequired[BucketLifecycleConfigurationTypeDef]
    ExpectedBucketOwner: NotRequired[str]
    TransitionDefaultMinimumObjectSize: NotRequired[TransitionDefaultMinimumObjectSizeType]


class PutBucketLifecycleConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    LifecycleConfiguration: NotRequired[BucketLifecycleConfigurationTypeDef]
    ExpectedBucketOwner: NotRequired[str]
    TransitionDefaultMinimumObjectSize: NotRequired[TransitionDefaultMinimumObjectSizeType]


class MetricsConfigurationTypeDef(TypedDict):
    Id: str
    Filter: NotRequired[MetricsFilterUnionTypeDef]


class ReplicationRuleTypeDef(TypedDict):
    Status: ReplicationRuleStatusType
    Destination: DestinationTypeDef
    ID: NotRequired[str]
    Priority: NotRequired[int]
    Prefix: NotRequired[str]
    Filter: NotRequired[ReplicationRuleFilterUnionTypeDef]
    SourceSelectionCriteria: NotRequired[SourceSelectionCriteriaTypeDef]
    ExistingObjectReplication: NotRequired[ExistingObjectReplicationTypeDef]
    DeleteMarkerReplication: NotRequired[DeleteMarkerReplicationTypeDef]


class GetBucketAnalyticsConfigurationOutputTypeDef(TypedDict):
    AnalyticsConfiguration: AnalyticsConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ListBucketAnalyticsConfigurationsOutputTypeDef(TypedDict):
    IsTruncated: bool
    ContinuationToken: str
    NextContinuationToken: str
    AnalyticsConfigurationList: List[AnalyticsConfigurationOutputTypeDef]
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketNotificationConfigurationRequestBucketNotificationPutTypeDef(TypedDict):
    NotificationConfiguration: NotificationConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]
    SkipDestinationValidation: NotRequired[bool]


class PutBucketNotificationConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    NotificationConfiguration: NotificationConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]
    SkipDestinationValidation: NotRequired[bool]


class RestoreObjectRequestObjectRestoreObjectTypeDef(TypedDict):
    VersionId: NotRequired[str]
    RestoreRequest: NotRequired[RestoreRequestTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class RestoreObjectRequestObjectSummaryRestoreObjectTypeDef(TypedDict):
    VersionId: NotRequired[str]
    RestoreRequest: NotRequired[RestoreRequestTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class RestoreObjectRequestRequestTypeDef(TypedDict):
    Bucket: str
    Key: str
    VersionId: NotRequired[str]
    RestoreRequest: NotRequired[RestoreRequestTypeDef]
    RequestPayer: NotRequired[Literal["requester"]]
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    ExpectedBucketOwner: NotRequired[str]


class GetBucketInventoryConfigurationOutputTypeDef(TypedDict):
    InventoryConfiguration: InventoryConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class ListBucketInventoryConfigurationsOutputTypeDef(TypedDict):
    ContinuationToken: str
    InventoryConfigurationList: List[InventoryConfigurationOutputTypeDef]
    IsTruncated: bool
    NextContinuationToken: str
    ResponseMetadata: ResponseMetadataTypeDef


class InventoryDestinationTypeDef(TypedDict):
    S3BucketDestination: InventoryS3BucketDestinationUnionTypeDef


class GetBucketReplicationOutputTypeDef(TypedDict):
    ReplicationConfiguration: ReplicationConfigurationOutputTypeDef
    ResponseMetadata: ResponseMetadataTypeDef


class PutBucketAnalyticsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    AnalyticsConfiguration: AnalyticsConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]


class PutBucketIntelligentTieringConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    IntelligentTieringConfiguration: IntelligentTieringConfigurationTypeDef


class PutBucketMetricsConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    MetricsConfiguration: MetricsConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]


ReplicationRuleUnionTypeDef = Union[ReplicationRuleTypeDef, ReplicationRuleOutputTypeDef]
InventoryDestinationUnionTypeDef = Union[
    InventoryDestinationTypeDef, InventoryDestinationOutputTypeDef
]


class ReplicationConfigurationTypeDef(TypedDict):
    Role: str
    Rules: Sequence[ReplicationRuleUnionTypeDef]


class InventoryConfigurationTypeDef(TypedDict):
    Destination: InventoryDestinationUnionTypeDef
    IsEnabled: bool
    Id: str
    IncludedObjectVersions: InventoryIncludedObjectVersionsType
    Schedule: InventoryScheduleTypeDef
    Filter: NotRequired[InventoryFilterTypeDef]
    OptionalFields: NotRequired[Sequence[InventoryOptionalFieldType]]


class PutBucketReplicationRequestRequestTypeDef(TypedDict):
    Bucket: str
    ReplicationConfiguration: ReplicationConfigurationTypeDef
    ChecksumAlgorithm: NotRequired[ChecksumAlgorithmType]
    Token: NotRequired[str]
    ExpectedBucketOwner: NotRequired[str]


class PutBucketInventoryConfigurationRequestRequestTypeDef(TypedDict):
    Bucket: str
    Id: str
    InventoryConfiguration: InventoryConfigurationTypeDef
    ExpectedBucketOwner: NotRequired[str]
