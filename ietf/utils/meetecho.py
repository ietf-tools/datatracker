# Copyright The IETF Trust 2021, All Rights Reserved
#
"""Meetecho interim meeting scheduling API

Implements the v1 API described in email from alex@meetecho.com
on 2021-12-09.

API methods return Python objects equivalent to the JSON structures
specified in the API documentation. Times and durations are represented
in the Python API by datetime and timedelta objects, respectively.
"""
import requests

import debug  # pyflakes: ignore

import datetime
from json import JSONDecodeError
from typing import Dict, Sequence, TypedDict, TYPE_CHECKING, Union
from urllib.parse import urljoin

# Guard against hypothetical cyclical import problems
if TYPE_CHECKING:
    from ietf.doc.models import Document
    from ietf.meeting.models import Session


class MeetechoAPI:
    timezone = datetime.timezone.utc

    def __init__(
        self, api_base: str, client_id: str, client_secret: str, request_timeout=3.01
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.request_timeout = request_timeout  # python-requests doc recommend slightly > a multiple of 3 seconds
        self._session = requests.Session()
        # if needed, add a trailing slash so urljoin won't eat the trailing path component
        self.api_base = api_base if api_base.endswith("/") else f"{api_base}/"

    def _request(self, method, url, api_token=None, json=None):
        """Execute an API request"""
        headers = {"Accept": "application/json"}
        if api_token is not None:
            headers["Authorization"] = f"bearer {api_token}"

        try:
            response = self._session.request(
                method,
                urljoin(self.api_base, url),
                headers=headers,
                json=json,
                timeout=self.request_timeout,
            )
        except requests.RequestException as err:
            raise MeetechoAPIError(str(err)) from err
        if response.status_code not in (200, 202):
            # Could be more selective about status codes, but not seeing an immediate need
            raise MeetechoAPIError(
                f"API request failed (HTTP status code = {response.status_code})"
            )

        # try parsing the result as JSON in case the server failed to set the Content-Type header
        try:
            return response.json()
        except JSONDecodeError as err:
            if response.headers.get("Content-Type", "").startswith("application/json"):
                # complain if server told us to expect JSON and it was invalid
                raise MeetechoAPIError("Error decoding response as JSON") from err
        return None

    def _deserialize_time(self, s: str) -> datetime.datetime:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=self.timezone)

    def _serialize_time(self, dt: datetime.datetime) -> str:
        return dt.astimezone(self.timezone).strftime("%Y-%m-%d %H:%M:%S")

    def _deserialize_duration(self, minutes: int) -> datetime.timedelta:
        return datetime.timedelta(minutes=minutes)

    def _serialize_duration(self, td: datetime.timedelta) -> int:
        return int(td.total_seconds() // 60)

    def _deserialize_meetings_response(self, response):
        """In-place deserialization of response data structure

        Deserializes data in the structure where needed (currently, that's time-related structures)
        """
        for session_data in response["rooms"].values():
            session_data["room"]["start_time"] = self._deserialize_time(
                session_data["room"]["start_time"]
            )
            session_data["room"]["duration"] = self._deserialize_duration(
                session_data["room"]["duration"]
            )
        return response

    def retrieve_wg_tokens(self, acronyms: Union[str, Sequence[str]]):
        """Retrieve API tokens for one or more WGs

        :param acronyms: list of WG acronyms for which tokens are requested
        :return: {'tokens': {acronym0: token0, acronym1: token1, ...}}
        """
        return self._request(
            "POST",
            "auth/ietfservice/tokens",
            json={
                "client": self.client_id,
                "secret": self.client_secret,
                "wgs": [acronyms] if isinstance(acronyms, str) else acronyms,
            },
        )

    def schedule_meeting(
        self,
        wg_token: str,
        description: str,
        start_time: datetime.datetime,
        duration: datetime.timedelta,
        extrainfo="",
    ):
        """Schedule a meeting session

        Return structure is:
          {
            "rooms": {
              "<session UUID>": {
                "room": {
                  "id": int,
                  "start_time": datetime,
                  "duration": timedelta
                  description: str,
                },
                "url": str,
                "deletion_token": str
              }
            }
          }

        :param wg_token: token retrieved via retrieve_wg_tokens()
        :param description: str describing the meeting
        :param start_time: starting time as a datetime
        :param duration: duration as a timedelta
        :param extrainfo: str with additional information for Meetecho staff
        :return: scheduled meeting data dict
        """
        return self._deserialize_meetings_response(
            self._request(
                "POST",
                "meeting/interim/createRoom",
                api_token=wg_token,
                json={
                    "description": description,
                    "start_time": self._serialize_time(start_time),
                    "duration": self._serialize_duration(duration),
                    "extrainfo": extrainfo,
                },
            )
        )

    def fetch_meetings(self, wg_token: str):
        """Fetch all meetings scheduled for a given wg

        Return structure is:
          {
            "rooms": {
              "<session UUID>": {
                "room": {
                  "id": int,
                  "start_time": datetime,
                  "duration": timedelta
                  "description": str,
                },
                "url": str,
                "deletion_token": str
              }
            }
          }

        As of 2022-01-31, the return structure also includes a 'group' key whose
        value is the group acronym. This is not shown in the documentation.

        :param wg_token: token from retrieve_wg_tokens()
        :return: meeting data dict
        """
        return self._deserialize_meetings_response(
            self._request("GET", "meeting/interim/fetchRooms", api_token=wg_token)
        )

    def delete_meeting(self, deletion_token: str):
        """Remove a scheduled meeting

        :param deletion_token: deletion_key from fetch_meetings() or schedule_meeting() return data
        :return: {}
        """
        return self._request(
            "POST", "meeting/interim/deleteRoom", api_token=deletion_token
        )

    class SlideDeckDict(TypedDict):
        id: int
        title: str
        url: str
        rev: str
        order: int

    def add_slide_deck(
        self, 
        wg_token: str,
        session: str,  # unique identifier
        deck: SlideDeckDict,
    ):
        """Add a slide deck for the specified session
        
        API spec:
       ⠀POST /materials
        + Authentication -> same as interim scheduler
        + content application/json
        + body
            {
                "session": String, // Unique session identifier
                "title": String,
                "id": Number,
                "url": String,
                "rev": String,
                "order": Number
            }
         
        + Results 
            202 Accepted 
            {4xx}
        """
        self._request(
            "POST",
            "materials",
            api_token=wg_token,
            json={
                "session": session,
                "title": deck["title"],
                "id": deck["id"],
                "url": deck["url"],
                "rev": deck["rev"],
                "order": deck["order"],
            },
        )

    def delete_slide_deck(
        self,
        wg_token: str,
        session: str, # unique identifier
        id: int, 
    ):
        """Delete a slide deck from the specified session

        API spec:
        DELETE /materials
        + Authentication -> same as interim scheduler
        + content application/json
        + body
            {
                "session": String,
                "id": Number
            }
         
        + Results 
            202 Accepted
            {4xx}
        """
        self._request(
            "DELETE",
            "materials",
            api_token=wg_token,
            json={
                "session": session,
                "id": id,
            },
        )

    def update_slide_decks(
        self,
        wg_token: str,
        session: str,  # unique id
        decks: list[SlideDeckDict],
    ):
        """Update/reorder decks for specified session

        PUT /materials
        + Authentication -> same as interim scheduler
        + content application/json
        + body
            {
                "session": String,
                "decks": [
                    {
                        "id": Number,
                        "title": String,
                        "url": String,
                        "rev": String,
                        "order": Number
                    },
                    {
                        "id": Number,
                        "title": String,
                        "url": String,
                        "rev": String,
                        "order": Number
                    },
                    ...
                ]
            }
         
        + Results 
            202 Accepted
        """
        self._request(
            "PUT",
            "materials",
            api_token=wg_token,
            json={
                "session": session,
                "decks": decks,
            }
        ) 


class MeetechoAPIError(Exception):
    """Base class for MeetechoAPI exceptions"""


class Conference:
    """Scheduled session/room representation"""

    def __init__(
        self,
        manager,
        id,
        public_id,
        description,
        start_time,
        duration,
        url,
        deletion_token,
    ):
        self._manager = manager
        self.id = id  # Meetecho system ID
        self.public_id = public_id  # public session UUID
        self.description = description
        self.start_time = start_time
        self.duration = duration
        self.url = url
        self.deletion_token = deletion_token

    @classmethod
    def from_api_dict(cls, manager, api_dict):
        # Returns a list of Conferences
        return [
            cls(
                **val["room"],
                public_id=public_id,
                url=val["url"],
                deletion_token=val["deletion_token"],
                manager=manager,
            )
            for public_id, val in api_dict.items()
        ]

    def __str__(self):
        return f"Meetecho conference {self.description}"

    def __repr__(self):
        props = [
            f'description="{self.description}"',
            f"start_time={repr(self.start_time)}",
            f"duration={repr(self.duration)}",
        ]
        return f'Conference({", ".join(props)})'

    def __eq__(self, other):
        return isinstance(other, type(self)) and all(
            getattr(self, attr) == getattr(other, attr)
            for attr in [
                "id",
                "public_id",
                "description",
                "start_time",
                "duration",
                "url",
                "deletion_token",
            ]
        )

    def delete(self):
        self._manager.delete_conference(self)


class APIConfigDict(TypedDict):
    api_base: str  # url
    client_id: str
    client_secret: str
    request_timeout: Union[float, int]


class Manager:
    def __init__(self, api_config: APIConfigDict):
        self.api = MeetechoAPI(**api_config)
        self.wg_tokens: Dict[str, str] = {}

    def wg_token(self, group):
        group_acronym = group.acronym if hasattr(group, "acronym") else group
        if group_acronym not in self.wg_tokens:
            self.wg_tokens[group_acronym] = self.api.retrieve_wg_tokens(group_acronym)[
                "tokens"
            ][group_acronym]
        return self.wg_tokens[group_acronym]


class ConferenceManager(Manager):
    def fetch(self, group):
        response = self.api.fetch_meetings(self.wg_token(group))
        return Conference.from_api_dict(self, response["rooms"])

    def create(self, group, description, start_time, duration, extrainfo=""):
        response = self.api.schedule_meeting(
            wg_token=self.wg_token(group),
            description=description,
            start_time=start_time,
            duration=duration,
            extrainfo=extrainfo,
        )
        return Conference.from_api_dict(self, response["rooms"])

    def delete_by_url(self, group, url):
        for conf in self.fetch(group):
            if conf.url == url:
                self.api.delete_meeting(conf.deletion_token)

    def delete_conference(self, conf: Conference):
        self.api.delete_meeting(conf.deletion_token)


class SlidesManager(Manager):
    def add(self, session: "Session", slides: "Document", order: int):
        self.api.add_slide_deck(
            wg_token=self.wg_token(session.group),
            session=str(session.pk),
            deck={
                "id": slides.pk,
                "title": slides.title,
                "url": slides.get_absolute_url(),
                "rev": slides.rev,
                "order": order,
            }
        )

    def delete(self, session: "Session", slides: "Document"):
        self.api.delete_slide_deck(
            wg_token=self.wg_token(session.group),
            session=str(session.pk),
            id=slides.pk,
        )
    
    def send_update(self, session: "Session"):
        self.api.update_slide_decks(
            wg_token=self.wg_token(session.group),
            session=str(session.pk),
            decks=[
                {
                    "id": deck.document.pk,
                    "title": deck.document.title,
                    "url": deck.document.get_absolute_url(),
                    "rev": deck.document.rev,
                    "order": deck.order,
                }
                for deck in session.presentations.filter(document__type="slides")
            ]
        )
