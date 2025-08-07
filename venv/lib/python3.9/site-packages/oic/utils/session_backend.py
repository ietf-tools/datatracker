import json
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import cast

from oic.utils.time_util import time_sans_frac


class AuthnEvent(object):
    def __init__(
        self,
        uid,
        salt,
        valid=3600,
        authn_info=None,
        time_stamp=0,
        authn_time=None,
        valid_until=None,
    ):
        """
        Create a representation of an authentication event.

        :param uid: The local user identifier
        :param salt: Salt to be used in creating a sub
        :param valid: How long the authentication is expected to be valid
        :param authn_info: Info about the authentication event
        :return:
        """
        self.uid = uid
        self.salt = salt
        self.authn_time = authn_time or (int(time_stamp) or time_sans_frac())
        self.valid_until = valid_until or (self.authn_time + int(valid))
        self.authn_info = authn_info

    def valid(self):
        return self.valid_until > time.time()

    def valid_for(self):
        return self.valid_until - time.time()

    def to_json(self):
        """Serialize AuthnEvent to JSON."""
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_struct):
        """Create AuthnEvent from JSON."""
        dic = json.loads(json_struct)
        return cls(**dic)


class SessionBackend(metaclass=ABCMeta):
    """Backend for storing sessionDB data."""

    @abstractmethod
    def __setitem__(self, key: str, value: Dict[str, Union[str, bool]]) -> None:
        """Store the session information under the session_id."""

    @abstractmethod
    def __getitem__(self, key: str) -> Dict[str, Union[str, bool]]:
        """
        Retrieve the session information based os session_id.

        @raises KeyError when no key is found.
        """

    @abstractmethod
    def __delitem__(self, key: str) -> None:
        """Remove the stored session from storage."""

    @abstractmethod
    def __contains__(self, key: str) -> bool:
        """Test presence of key in storage."""

    @abstractmethod
    def get_by_uid(self, uid: str) -> List[str]:
        """Return session ids (keys) based on `uid` (internal user identifier)."""

    @abstractmethod
    def get_by_sub(self, sub: str) -> List[str]:
        """Return session ids based on `sub` (external user identifier)."""

    @abstractmethod
    def get(self, attr: str, val: str) -> List[str]:
        """Return session ids based on attribute name and value."""

    def get_client_ids_for_uid(self, uid: str) -> List[str]:
        """Return client ids that have a session for given uid."""
        return [cast(str, self[sid]["client_id"]) for sid in self.get_by_uid(uid)]

    def get_verified_logout(self, uid: str) -> Optional[str]:
        """Return logout verification key for given uid."""
        # Since all the sessions should be the same, we return the first one
        sids = self.get_by_uid(uid)
        if len(sids) == 0:
            return None
        _dict = self[sids[0]]
        if "verified_logout" not in _dict:
            return None
        return cast(str, _dict["verified_logout"])

    def get_token_ids(self, uid: str) -> List[str]:
        """Return id_tokens for the given uid."""
        return [cast(str, self[sid]["id_token"]) for sid in self.get_by_uid(uid)]

    def is_revoke_uid(self, uid: str) -> bool:
        """Return if the session is revoked."""
        # We do not care which session it is - once revoked, al are revoked
        return any([self[sid]["revoked"] for sid in self.get_by_uid(uid)])

    def update(self, key: str, attribute: str, value: Any):
        """
        Update information stored. If the key is not know a new entry will be constructed.

        :param key: Key to the database
        :param attribute: Attribute name
        :param value: Attribute value
        """
        if key not in self:
            self[key] = {attribute: value}
        else:
            item = self[key]
            item[attribute] = value
            self[key] = item

    def get_uid_by_sub(self, sub: str) -> Optional[str]:
        """Return User id based on sub."""
        for sid in self.get_by_sub(sub):
            return AuthnEvent.from_json(self[sid]["authn_event"]).uid
        return None

    def get_uid_by_sid(self, sid: str) -> str:
        """Return User id based on session ID."""
        return AuthnEvent.from_json(self[sid]["authn_event"]).uid


class DictSessionBackend(SessionBackend):
    """
    Simple implementation of `SessionBackend` based on dictionary.

    This should really not be used in production.
    """

    def __init__(self):
        """Create the storage."""
        self.storage: Dict[str, Dict[str, Union[str, bool]]] = {}

    def __setitem__(self, key: str, value: Dict[str, Union[str, bool]]) -> None:
        """Store the session info in the storage."""
        self.storage[key] = value

    def __getitem__(self, key: str) -> Dict[str, Union[str, bool]]:
        """Retrieve session information based on session id."""
        return self.storage[key]

    def __delitem__(self, key: str) -> None:
        """Delete the session info."""
        del self.storage[key]

    def __contains__(self, key: str) -> bool:
        return key in self.storage

    def get_by_sub(self, sub: str) -> List[str]:
        """Return session ids based on sub."""
        return [
            sid for sid, session in self.storage.items() if session.get("sub") == sub
        ]

    def get_by_uid(self, uid: str) -> List[str]:
        """Return session ids based on uid."""
        return [
            sid
            for sid, session in self.storage.items()
            if AuthnEvent.from_json(session["authn_event"]).uid == uid
        ]

    def get(self, attr: str, val: str) -> List[str]:
        """Return session ids based on attribute name and value."""
        return [
            sid for sid, session in self.storage.items() if session.get(attr) == val
        ]
