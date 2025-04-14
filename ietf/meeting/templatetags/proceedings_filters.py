# Copyright The IETF Trust 2016-2020, All Rights Reserved
from django import template

import debug  # pyflakes:ignore

register = template.Library()


@register.filter
def hack_recording_title(recording, add_timestamp=False):

    if recording.title.startswith("Audio recording for") or recording.title.startswith(
        "Video recording for"
    ):
        hacked_title = recording.title[:15]
        if add_timestamp:
            hacked_title += (
                " "
                + recording.presentations.first()
                .session.official_timeslotassignment()
                .timeslot.time.strftime("%a %H:%M")
            )
        return hacked_title
    else:
        return recording.title


@register.filter
def status_for_meeting(group, meeting):
    return group.status_for_meeting(meeting)


@register.filter
def meeting_href(doc, meeting):
    return doc.get_href(meeting)
