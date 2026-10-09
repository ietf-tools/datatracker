# Copyright The IETF Trust 2026, All Rights Reserved
"""In-memory fake of the Typesense client for tests

Covers the parts of typesense.Client that ietf.utils.search_provider uses. Patch it
in with

    fake = FakeTypesenseClient()
    with mock.patch("ietf.utils.search_provider.typesense.Client", return_value=fake):
        ...

so that every client the code under test creates shares the same state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import typesense.exceptions


@dataclass
class FakeCollection:
    schema: dict[str, Any]
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)


class FakeTypesenseClient:
    """Fake typesense.Client

    Tests can inspect and modify `collection_data` and `alias_data` directly.

    Hooks for simulating concurrent activity or errors:
    * `before_write(collection_name)` is called before each document write or
      import; it may modify state or raise.
    * `before_delete(collection_name)` is called before each collection delete; it
      may modify state or raise.
    * `document_errors` maps (collection_name, document id) to an error message;
      importing that document fails with code 400.
    """

    def __init__(self) -> None:
        self.collection_data: dict[str, FakeCollection] = {}
        self.alias_data: dict[str, str] = {}
        self.before_write: Callable[[str], None] | None = None
        self.before_delete: Callable[[str], None] | None = None
        self.document_errors: dict[tuple[str, str], str] = {}
        self.collections = _Collections(self)
        self.aliases = _Aliases(self)

    def add_collection(self, name, schema=None, documents=()):
        self.collection_data[name] = FakeCollection(
            schema={} if schema is None else schema,
            documents={doc["id"]: dict(doc) for doc in documents},
        )

    def documents(self, collection_name) -> dict[str, dict[str, Any]]:
        return self.collection_data[collection_name].documents

    def _resolve(self, name):
        """Resolve a collection name or alias as Typesense does"""
        if name in self.collection_data:
            return name
        target = self.alias_data.get(name)
        if target is not None and target in self.collection_data:
            return target
        raise typesense.exceptions.ObjectNotFound(f"No collection named {name}")

    def _before_write(self, name):
        if self.before_write is not None:
            self.before_write(name)


class _Collections:
    def __init__(self, client):
        self._client = client

    def retrieve(self):
        return [
            {"name": name} | collection.schema
            for name, collection in self._client.collection_data.items()
        ]

    def create(self, schema):
        schema = dict(schema)
        name = schema.pop("name")
        if name in self._client.collection_data:
            raise typesense.exceptions.ObjectAlreadyExists(
                f"A collection with name `{name}` already exists."
            )
        self._client.add_collection(name, schema)
        return {"name": name} | schema

    def __getitem__(self, name):
        return _CollectionRef(self._client, name)


class _CollectionRef:
    def __init__(self, client, name):
        self._client = client
        self._name = name
        self.documents = _Documents(client, name)

    def delete(self):
        if self._client.before_delete is not None:
            self._client.before_delete(self._name)
        if self._name not in self._client.collection_data:
            raise typesense.exceptions.ObjectNotFound(f"No collection {self._name}")
        del self._client.collection_data[self._name]


class _Documents:
    def __init__(self, client, name):
        self._client = client
        self._name = name

    def upsert(self, document):
        self._client._before_write(self._name)
        collection = self._client._resolve(self._name)
        self._client.documents(collection)[document["id"]] = dict(document)
        return document

    def import_(self, documents, params):
        self._client._before_write(self._name)
        collection = self._client._resolve(self._name)
        stored = self._client.documents(collection)
        action = params["action"]
        results = []
        for document in documents:
            doc_id = document["id"]
            error = self._client.document_errors.get((collection, doc_id))
            if error is not None:
                results.append(
                    {
                        "success": False,
                        "error": error,
                        "code": 400,
                        "document": document,
                    }
                )
            elif action == "create" and doc_id in stored:
                results.append(
                    {
                        "success": False,
                        "error": f"A document with id {doc_id} already exists.",
                        "code": 409,
                        "document": document,
                    }
                )
            elif action == "update" and doc_id not in stored:
                results.append(
                    {
                        "success": False,
                        "error": f"Could not find a document with id: {doc_id}",
                        "code": 404,
                        "document": document,
                    }
                )
            else:
                if action == "update":
                    stored[doc_id].update(document)
                else:
                    stored[doc_id] = dict(document)
                results.append({"success": True})
        return results


class _Aliases:
    def __init__(self, client):
        self._client = client

    def upsert(self, name, mapping):
        if name in self._client.collection_data:
            raise typesense.exceptions.ServerError(
                f"Name `{name}` conflicts with an existing collection name."
            )
        self._client.alias_data[name] = mapping["collection_name"]
        return {"name": name} | mapping

    def __getitem__(self, name):
        return _AliasRef(self._client, name)


class _AliasRef:
    def __init__(self, client, name):
        self._client = client
        self._name = name

    def retrieve(self):
        if self._name not in self._client.alias_data:
            raise typesense.exceptions.ObjectNotFound(f"No alias {self._name}")
        return {
            "name": self._name,
            "collection_name": self._client.alias_data[self._name],
        }

    def delete(self):
        if self._name not in self._client.alias_data:
            raise typesense.exceptions.ObjectNotFound(f"No alias {self._name}")
        return {
            "name": self._name,
            "collection_name": self._client.alias_data.pop(self._name),
        }
