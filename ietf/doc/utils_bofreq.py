# Copyright The IETF Trust 2021 All Rights Reserved

from ietf.doc.models import BofreqEditorDocEvent, BofreqResponsibleDocEvent
from ietf.person.models import Person

def bofreq_editors(bofreq):
    e = bofreq.latest_event(BofreqEditorDocEvent)
    return e.editors.all() if e else Person.objects.none()

def bofreq_responsible(bofreq):
    e = bofreq.latest_event(BofreqResponsibleDocEvent)
    return e.responsible.all() if e else Person.objects.none()