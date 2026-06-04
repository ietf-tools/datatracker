# Copyright The IETF Trust 2026, All Rights Reserved
from typing import Optional, Union, Any

from django.core.cache import BaseCache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django_redis.client import DefaultClient, SentinelClient
from redis import Redis
from redis.typing import KeyT, EncodableT

from ietf.utils.log import log


class EncodedValueTooBig(ValueError):
    def __init__(self, *args, value_len):
        super().__init__(*args)
        self.value_len = value_len


class SizeLimitingRedisClient(DefaultClient):
    """Redis DefaultClient that refuses to cache large objects
    
    Size applies to the literal cached value, which is _after_ serialization and
    compression.
    
    Set size limit with MAX_ENCODED_VALUE_LEN in the OPTIONS dict. Defaults to
    1 MB.
    """
    def __init__(self, server, params: dict[str, Any], backend: BaseCache) -> None:
        super().__init__(server, params, backend)
        self.max_encoded_value_len = self._options.get("MAX_ENCODED_VALUE_LEN", 1 << 20)

    def encode(self, value: EncodableT) -> Union[bytes, int]:
        encoded = super().encode(value)
        if isinstance(encoded, bytes) and len(encoded) > self.max_encoded_value_len:
            raise EncodedValueTooBig(value_len=len(encoded))
        return encoded

    def set(
        self,
        key: KeyT,
        value: EncodableT,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        version: Optional[int] = None,
        client: Optional[Redis] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        try:
            return super().set(key, value, timeout, version, client, nx, xx)
        except EncodedValueTooBig as err:
            log(
                f"Refused to cache large object for {key!r} "
                f"({err.value_len} > {self.max_encoded_value_len} bytes)"
            )
            return False


class SizeLimitingSentinelClient(SizeLimitingRedisClient, SentinelClient):
    """Redis SentinelClient that refuses to cache large objects
    
    Size applies to the literal cached value, which is _after_ serialization and
    compression.
        
    Set size limit with MAX_ENCODED_VALUE_LEN in the OPTIONS dict. Defaults to
    1 MB.
    """
    pass
