from django import template

register = template.Library()

@register.filter
def hack_recording_title(recording,add_timestamp=False):
   
   if recording.title.startswith('Audio recording for') or recording.title.startswith('Video recording for'):
       hacked_title = recording.title[:15]
       if add_timestamp:
           hacked_title += ' '+recording.sessionpresentation_set.first().session.official_timeslotassignment().timeslot.time.strftime("%a %H:%M")
       return hacked_title
   else:
       return recording.title

@register.filter
def status_for_meeting(group,meeting):
    return group.status_for_meeting(meeting)
