# -*- python -*-

import re
from typing import Any, List
import tastypie

blobdb          = ...       # type: Any
community       = ...       # type: Any
dbtemplate      = ...       # type: Any
doc             = ...       # type: Any
group           = ...       # type: Any
idindex         = ...       # type: Any
iesg            = ...       # type: Any
ietfauth        = ...       # type: Any
ipr             = ...       # type: Any
liaisons        = ...       # type: Any
mailinglists    = ...       # type: Any
mailtrigger     = ...       # type: Any
meeting         = ...       # type: Any
message         = ...       # type: Any
name            = ...       # type: Any
nomcom          = ...       # type: Any
person          = ...       # type: Any
redirects       = ...       # type: Any
release         = ...       # type: Any
review          = ...       # type: Any
stats           = ...       # type: Any
submit          = ...       # type: Any
sync            = ...       # type: Any
utils           = ...       # type: Any

_api_list                 = ...       # type: List
OMITTED_APPS_APIS         = ...       # type: List[str]
HAVE_BROKEN_FROMISOFORMAT = ...       # type: bool
TIMEDELTA_REGEX           = ...       # type: re.Pattern[str]
_XML_INVALID_CTRL_RE      = ...       # type: re.Pattern[str]
_XML_INVALID_UNICODE_RE   = ...       # type: re.Pattern[str]

class ModelResource(tastypie.resources.ModelResource): ...
class Serializer(): ...
class ToOneField(tastypie.fields.ToOneField): ...
class TimedeltaField(tastypie.fields.ApiField): ...

def populate_api_list() -> None: ...
def autodiscover() -> None: ...
