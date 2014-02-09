#!/usr/bin/env python
from ietf import settings
from django.core import management
management.setup_environ(settings)

from ietf.doc.models import RelatedDocument,State,DocEvent
from ietf.person.models import Person


relevant_relations = RelatedDocument.objects.filter(relationship__slug='replaces',
                                                    target__document__type__slug='draft',
                                                    target__document__states__type='draft',
                                                    target__document__states__slug__in=['active','expired'])

affected_docs = set([x.target.document for x in relevant_relations])

replaced_state = State.objects.get(type='draft',slug='repl')

system_user = Person.objects.get(name="(System)")

for d in affected_docs:
    d.set_state(replaced_state)
    DocEvent.objects.create(type="added_comment",
                            doc=d,
                            by=system_user,
                            desc='Draft state administratively corrected to Replaced',
                           )

