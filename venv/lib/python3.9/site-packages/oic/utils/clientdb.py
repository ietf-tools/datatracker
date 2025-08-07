"""Client management databases."""

from abc import ABCMeta
from abc import abstractmethod
from urllib.parse import quote
from urllib.parse import urljoin

import requests

from oic.oauth2.exception import NoClientInfoReceivedError


class BaseClientDatabase(metaclass=ABCMeta):
    """
    Base implementation for Client management database.

    Custom Client databases should derive from this class.
    They must implement the following methods:
    * ``__getitem__(self, key)``
    * ``__setitem__(self, key, value)``
    * ``__delitem__(self, key)``
    * ``keys(self)``
    * ``items(self)``
    """

    def __init__(self):
        """Perform initialization of storage. Derived classes may override."""

    @abstractmethod
    def __getitem__(self, key):
        """Retrieve an item by a key. Raises KeyError if item not found."""
        pass  # pragma: no cover

    def get(self, key, default=None):
        """Retrieve an item by a key. Return default if not found."""
        try:
            return self[key]
        except KeyError:
            return default

    @abstractmethod
    def __setitem__(self, key, value):
        """Set key with value."""
        pass  # pragma: no cover

    @abstractmethod
    def __delitem__(self, key):
        """Remove key from database."""
        pass  # pragma: no cover

    def __contains__(self, key):
        """Return True if key is contained in the database."""
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    @abstractmethod
    def keys(self):
        """Return all contained keys."""
        pass  # pragma: no cover

    @abstractmethod
    def items(self):
        """Return list of all contained items."""
        pass  # pragma: no cover

    def __len__(self):
        """Return number of contained keys."""
        return len(self.keys())


class MDQClient(BaseClientDatabase):
    """Implementation of remote client database."""

    def __init__(self, url, timeout=5):
        """Set the remote storage url and timeout for requests."""
        self.url = url
        self.timeout = timeout
        self.headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}

    def __getitem__(self, item):
        """Retrieve a single entity."""
        mdx_url = urljoin(self.url, "entities/{}".format(quote(item, safe="")))
        response = requests.get(mdx_url, headers=self.headers, timeout=self.timeout)
        if response.status_code == 200:
            return response.json()
        else:
            raise NoClientInfoReceivedError(
                "{} {}".format(response.status_code, response.reason)
            )

    def __setitem__(self, item, value):
        """Remote management is readonly."""
        raise RuntimeError("MDQClient is readonly.")

    def __delitem__(self, item):
        """Remote management is readonly."""
        raise RuntimeError("MDQClient is readonly.")

    def keys(self):
        """Get all registered entitites."""
        mdx_url = urljoin(self.url, "entities")
        response = requests.get(mdx_url, headers=self.headers, timeout=self.timeout)
        if response.status_code == 200:
            return [item["client_id"] for item in response.json()]
        else:
            raise NoClientInfoReceivedError(
                "{} {}".format(response.status_code, response.reason)
            )

    def items(self):
        """Geting all registered entities."""
        mdx_url = urljoin(self.url, "entities")
        response = requests.get(mdx_url, headers=self.headers, timeout=self.timeout)
        if response.status_code == 200:
            return response.json()
        else:
            raise NoClientInfoReceivedError(
                "{} {}".format(response.status_code, response.reason)
            )


# Dictionary can be used as a ClientDatabase
BaseClientDatabase.register(dict)
