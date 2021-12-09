# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""HedgeDoc API utilities"""
import json
import requests
import subprocess
import debug  # pyflakes: ignore

from urllib.parse import urljoin
from django.conf import settings

from ietf.utils.markdown import markdown


class Note:
    base_url = settings.IETF_NOTES_URL

    def __init__(self, id):
        self.id = id
        self.url = urljoin(self.base_url, self.id)  # URL on notes site
        self._metadata = None
        self._preview = None
        self._source = None

    @classmethod
    def preprocess_source(cls, raw_source):
        """Perform preprocessing on raw source input

        Guaranteed to process input in the same way that the Note class processes
        markdown source pulled from the notes site.
        """
        return de_gfm(raw_source)

    def get_source(self):
        """Retrieve markdown source from hedgedoc

        Converts line breaks from GitHub Flavored Markdown (GFM) style to
        to traditional markdown.
        """
        if self._source is None:
            try:
                r = requests.get(urljoin(self.base_url, f'{self.id}/download'), allow_redirects=True)
            except requests.RequestException:
                raise ServerNoteError
            if r.status_code != 200:
                raise NoteNotFound
            self._source = self.preprocess_source(r.text)
        return self._source

    def get_preview(self):
        if self._preview is None:
            self._preview = markdown(self.get_source())
        return self._preview

    def get_title(self):
        try:
            metadata = self._retrieve_metadata()
        except NoteError:
            metadata = {}  # don't let an error retrieving the title prevent retrieval
        return metadata.get('title', None)

    def get_update_time(self):
        try:
            metadata = self._retrieve_metadata()
        except NoteError:
            metadata = {}  # don't let an error retrieving the update timestamp prevent retrieval
        return metadata.get('updatetime', None)

    def _retrieve_metadata(self):
        if self._metadata is None:
            try:
                r = requests.get(urljoin(self.base_url, f'{self.id}/info'), allow_redirects=True)
            except requests.RequestException:
                raise ServerNoteError
            if r.status_code != 200:
                raise NoteNotFound
            try:
                self._metadata = json.loads(r.content)
            except json.JSONDecodeError:
                raise InvalidNote
        return self._metadata


def de_gfm(source: str):
    """Convert GFM line breaks to standard Markdown

    Calls de-gfm from the kramdown-rfc2629 gem.
    """
    result = subprocess.run(
        [settings.DE_GFM_BINARY,],
        stdout=subprocess.PIPE,  # post-Python 3.7, this can be replaced with capture_output=True
        input=source,
        encoding='utf8',
        check=True,
    )
    return result.stdout


class NoteError(Exception):
    """Base class for exceptions in this module"""
    default_message = 'A note-related error occurred'

    def __init__(self, *args, **kwargs):
        if not args:
            args = (self.default_message, )
        super().__init__(*args)


class ServerNoteError(NoteError):
    default_message = 'Could not reach the notes server'

class NoteNotFound(NoteError):
    default_message = 'Note did not exist or could not be loaded'


class InvalidNote(NoteError):
    default_message = 'Note data invalid'