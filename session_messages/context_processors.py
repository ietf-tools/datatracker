"""
Context processor for lightweight session messages.

Time-stamp: <2008-07-19 23:16:19 carljm context_processors.py>

"""
from django.utils.encoding import StrAndUnicode

from session_messages import get_and_delete_messages

def session_messages (request):
    """
    Returns session messages for the current session.

    """
    return { 'session_messages': LazyMessages(request) }

class LazyMessages (StrAndUnicode):
    """
    Lazy message container, so messages aren't actually retrieved from
    session and deleted until the template asks for them.

    """
    def __init__(self, request):
        self.request = request

    def __iter__(self):
        return iter(self.messages)

    def __len__(self):
        return len(self.messages)

    def __nonzero__(self):
        return bool(self.messages)

    def __unicode__(self):
        return unicode(self.messages)

    def __getitem__(self, *args, **kwargs):
        return self.messages.__getitem__(*args, **kwargs)

    def _get_messages(self):
        if hasattr(self, '_messages'):
            return self._messages
        self._messages = get_and_delete_messages(self.request)
        return self._messages
    messages = property(_get_messages)
    
