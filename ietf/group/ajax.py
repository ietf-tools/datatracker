from django.utils import simplejson as json
from dajaxice.core import dajaxice_functions
from dajaxice.decorators import dajaxice_register
from ietf.ietfauth.decorators import group_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, Http404

from ietf.group.models import Group
import datetime
import logging
import sys
from ietf.settings import LOG_DIR

log = logging.getLogger(__name__)

def group_json(request, groupname):
    group = get_object_or_404(Group, acronym=groupname)

    #print "group request is: %s\n" % (request.build_absolute_uri('/'))
    return HttpResponse(json.dumps(group.json_dict(request.build_absolute_uri('/')),
                                   sort_keys=True, indent=2),
                        mimetype="text/json")

