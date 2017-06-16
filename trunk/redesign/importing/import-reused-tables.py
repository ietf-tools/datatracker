#!/usr/bin/python

# boiler plate
import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

# script

from django.db.models import TextField, CharField

from django.contrib.sites.models import Site
from ietf.redirects.models import Redirect, Suffix, Command
from ietf.iesg.models import TelechatAgendaItem, WGAction
from ietf.ipr.models import IprSelecttype, IprLicensing, IprDetail, IprContact, IprNotification, IprUpdate
from ietf.submit.models import IdSubmissionStatus, IdSubmissionDetail, IdApprovedDetail, TempIdAuthors
from django.contrib.auth.models import User

known_models = {
    'base': [User],
    'others': [Site,
               Redirect, Suffix, Command,
               TelechatAgendaItem, WGAction,
               IprSelecttype, IprLicensing, IprDetail, IprContact, IprNotification, IprUpdate,
               IdSubmissionStatus, IdSubmissionDetail, IdApprovedDetail,
               TempIdAuthors]
    }

models_to_copy = known_models[sys.argv[1]]

def queryset_chunks(q, n):
    """Split queryset q up in chunks of max size n."""
    return (q[i:i+n] for i in range(0, q.count(), n))

def insert_many_including_pk(objects, using="default", table=None):
    """Insert list of Django objects in one SQL query. Objects must be
    of the same Django model. Note that save is not called and signals
    on the model are not raised."""
    if not objects:
        return

    import django.db.models
    from django.db import connections
    con = connections[using]
    
    model = objects[0].__class__
    fields = [f for f in model._meta.fields]
    parameters = []
    for o in objects:
        pars = []
        for f in fields:
            pars.append(f.get_db_prep_save(f.pre_save(o, True), connection=con))
        parameters.append(pars)

    if not table:
        table = model._meta.db_table
    column_names = ",".join(con.ops.quote_name(f.column) for f in fields)
    placeholders = ",".join(("%s",) * len(fields))
    con.cursor().executemany(
        "replace into %s (%s) values (%s)" % (table, column_names, placeholders),
        parameters)

def clean_chunk(model, chunk):
    for o in chunk:
        if model == IprDetail:
            if o.applies_to_all == "":
                o.applies_to_all = None

        for f in model._meta.fields:
            # change non-nullable nulls on string fields to ""
            if type(f) in (CharField, TextField) and not f.null and getattr(o, f.name) == None:
                setattr(o, f.name, "")

for model in models_to_copy:
    sys.stdout.write("copying %s " % model._meta.object_name)
    sys.stdout.flush()

    irregular_models = [Site]
    if model in irregular_models:
        table_name = Site._meta.db_table
    else:
        table_name = "%s_%s" % (model._meta.app_label, model._meta.object_name.lower())

    for chunk in queryset_chunks(model.objects.using("legacy").all(), 1000):
        clean_chunk(model, chunk)
        insert_many_including_pk(chunk, using="default", table=table_name)
        sys.stdout.write(".")
        sys.stdout.flush()

    sys.stdout.write("\n")
