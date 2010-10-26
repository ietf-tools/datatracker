#!/usr/bin/python

# boiler plate
import os, sys

one_dir_up = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))

sys.path.insert(0, one_dir_up)

from django.core.management import setup_environ
import settings
setup_environ(settings)

# script
from django.core.serializers import serialize
from django.db.models import Q 
from idtracker.models import *
from iesg.models import *

def output(name, qs):
    try:
        f = open(os.path.join(settings.BASE_DIR, "idrfc/fixtures/%s.xml" % name), 'w')
        f.write(serialize("xml", qs, indent=4))
        f.close()
    except:
        from django.db import connection
        from pprint import pprint
        pprint(connection.queries)
        raise

# base data
base = []
    
area_directors = AreaDirector.objects.all()
broken_logins = ('bthorson', 'members', 'iab')

base.extend(area_directors)
base.extend(PersonOrOrgInfo.objects.filter(areadirector__in=area_directors))
base.extend(IESGLogin.objects.filter(Q(login_name="klm") | Q(person__in=[a.person for a in area_directors])).exclude(login_name__in=broken_logins))
base.extend(EmailAddress.objects.filter(person_or_org__areadirector__in=area_directors, priority=1))
base.extend(IDStatus.objects.all())
base.extend(IDIntendedStatus.objects.all())
base.extend(IDSubState.objects.all())
base.extend(IDState.objects.all())
base.extend(WGType.objects.all())
base.extend(TelechatDates.objects.all())
base.extend(Acronym.objects.filter(acronym_id=Acronym.INDIVIDUAL_SUBMITTER))
base.extend(IDDates.objects.all())

output("base", base)


# specific drafts
draftdata = []
d = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
draftdata.extend([d, d.idinternal, d.group, d.group.ietfwg])
ags = AreaGroup.objects.filter(group__exact=d.group.ietfwg.group_acronym)
draftdata.extend(ags)
draftdata.extend([a.area for a in ags])
draftdata.extend([a.area.area_acronym for a in ags])
d = InternetDraft.objects.get(filename="draft-ietf-mip6-cn-ipsec")
draftdata.extend([d, d.idinternal])
d = InternetDraft.objects.get(filename="draft-ah-rfc2141bis-urn")
draftdata.extend([d, d.group, d.group.ietfwg])
output("draft", draftdata)

# specific ballot info
d = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
output("ballot", [d.idinternal.ballot]) 


# specific WG actions
wgas = WGAction.objects.all()
output("wgactions", list(wgas) + list(Acronym.objects.filter(wgaction__in=wgas)) + [Acronym.objects.get(acronym="sieve")])
