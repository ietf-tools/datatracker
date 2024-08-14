# -*- python -*-

from typing import Any, List
import tastypie

community       = ...       # type: Any
dbtemplate      = ...       # type: Any
doc             = ...       # type: Any
group           = ...       # type: Any
iesg            = ...       # type: Any
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
review          = ...       # type: Any
stats           = ...       # type: Any
submit          = ...       # type: Any
utils           = ...       # type: Any

_api_list       = ...       # type: List

class ModelResource(tastypie.resources.ModelResource): ...
class Serializer(): ...
class ToOneField(tastypie.fields.ToOneField): ...
class TimedeltaField(tastypie.fields.ApiField): ...

def populate_api_list() -> None: ...
def autodiscover() -> None: ...
