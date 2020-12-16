# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import json
import os.path
import pytz
import sys
import time
import warnings

from django.apps import registry
from django.conf import settings
from django.db import migrations
from django.db import models

import debug                            # pyflakes:ignore

from ietf.api import Serializer


warnings.filterwarnings("ignore", message=r"group\.HistoricalGroupFeatures\.\w+ failed to load invalid json")

# ----------------------------------------------------------------------

def forward(apps, schema_editor):
    tzfrom = pytz.timezone(settings.TIME_ZONE)
    tzto   = pytz.utc
    convert(apps, tzfrom, tzto)

def reverse(apps, schema_editor):
#     tzfrom = pytz.utc
#     tzto   = pytz.timezone(settings.TIME_ZONE)
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('utils', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]

# ----------------------------------------------------------------------

inv_count = 0
converted = { "": 0, }
unchanged = { "": 0, }
nonevalue = { "": 0, }
meeting_tz = { "": pytz.utc }

def nowstr():
    return datetime.datetime.now().isoformat(timespec='seconds')

def read_field_inventory(datafn):
    note(f"{nowstr()} Reading datetime field inventory:")
    values = {}
    if not os.path.exists(datafn) or os.path.getsize(datafn) == 0:
        # Save empty content
        with open(datafn, "w") as f:
            json.dump(values, f, default=Serializer)
            note("  Saved initial empty datetime field inventory")
    with open(datafn, "r") as f:
        try:
            note("  Reading existing inventory...")
            values = json.load(f)
        except json.decoder.JSONDecodeError as e:
            sys.stderr.write(e)
    return values

def note(msg):
    sys.stderr.write('%s\n' % msg)

def convert(apps, tzfrom, tzto):
    global inv_count
    settings.USE_TZ = False
    settings.SERVER_MODE = 'repair'
    datafn = "datetime-fields.json"
    values = read_field_inventory(datafn)
    error = None

    note(f"{nowstr()} Doing inventory of unconverted datetime field values:")
    sys.stderr.write('    Objects       New   Time   Loop\n')
    try:
        for appname, appconf in registry.apps.app_configs.items():
            for model in appconf.get_models():
                do_field_inventory(model, apps, values)
    except KeyboardInterrupt as e:
        note("Keyboard interrupt")
        error = e
    finally:
        if values and inv_count:
            with open(datafn, "w") as f:
                json.dump(values, f)
                note(f"  Saved {inv_count} new unconverted datetime field values")
        else:
            note("  No new unconverted datetime field values")
    if error:
        sys.exit(error)


    note(f"{nowstr()} Converting datetime fields from {tzfrom} to {tzto}:")
    sys.stderr.write('    Objects Converted   Time   Loop\n')
    try:
        for appname, appconf in registry.apps.app_configs.items():
            for model in appconf.get_models():
                # Get an unvarnished version of the model
                model = apps.get_model(appname, model.__name__)
                convert_fields(model, apps, values, tzfrom, tzto)
    except KeyboardInterrupt as e:
        note("Keyboard interrupt")
        error = e
    finally:
        note(f"{nowstr()} Done converting timestamps.")
    if error:
        sys.exit(error)

def has_datetime(model, parents):
    has_datetime = False
    for field in model._meta.fields:
        if isinstance(field, models.DateTimeField):
            # Don't double convert fields inherited from a parent class (this is
            # simplified, and doesn't deal correctly with subclass fields that
            # shadow fields of the same name in a parent class ):
            if not ( parents and all([ field.name in [ f.name for f in p._meta.fields ] for p in parents ]) ):
                has_datetime = True
    return has_datetime

def do_field_inventory(model, apps, values):
    global inv_count

    parents = model._meta.get_parent_list()
    if not has_datetime(model, parents):
        return

    app_label = model._meta.app_label
    model_name = model.__name__


    objects = model.objects.all()
    count = objects.count()
    mark = time.time()

    if count == 0:
        return

    m = f"{app_label}.{model_name}"

    for c in [converted, unchanged, nonevalue, ]:
        if not m in c:
            c[m] = 0
    sys.stderr.write(f'  {count:9,} ......... ...... ...... {m}\r')

    inv_mark = inv_count
    for o in objects:
        for field in model._meta.fields:
            if isinstance(field, models.DateTimeField):
                value = getattr(o, field.name)
                if not value:
                    continue
                if any([field.name in [ f.name for f in p._meta.fields ] for p in parents ]):
                    continue
                f = f"{app_label}.{model_name}.{field.name}"
                this = value.isoformat(timespec='microseconds')

                # Update our inventory of pre-conversion field values as needed
                for c in [values, ]:
                    if not f in c:
                        c[f] = {}
                k = str(o.pk)
                if not k in values[f]:
                    values[f][k] = this
                    inv_count += 1

    tau = time.time()-mark
    if count:
        looptime = (tau)*10**6/count
        sys.stderr.write(f'  {count:9,} {inv_count-inv_mark:9,} {tau:5.1f}s {looptime:4.0f}µs\n')
    else:
        sys.stderr.write(f'  {count:9,} {0:9,} {tau:5.1f}s {0:4.0f}µs\n')

    return values

def convert_fields(model, apps, values, tzfrom, tzto):
    global inv_count, converted, unchanged, nonevalue

    parents = model._meta.get_parent_list()
    if not has_datetime(model, parents):
        return

    app_label = model._meta.app_label
    model_name = model.__name__

    objects = model.objects.all()
    count = objects.count()
    mark = time.time()

    if count == 0:
        return

    m = f"{app_label}.{model_name}"

    for c in [converted, unchanged, nonevalue, ]:
        if not m in c:
            c[m] = 0
    sys.stderr.write(f'  {count:9,} ......... ...... ...... {m}\r')

    for o in objects:
        for field in model._meta.fields:
            if isinstance(field, models.DateTimeField):
                value = getattr(o, field.name)
                if not value:
                    continue
                if any([field.name in [ f.name for f in p._meta.fields ] for p in parents ]):
                    continue
                f = f"{app_label}.{model_name}.{field.name}"
                k = str(o.pk)
                this = value.isoformat(timespec='microseconds')

                # Convert field
                orig = values[f][k] if k in values[f] else None
                if this and this == orig:
                    try:
                        if model_name == 'TimeSlot':
                            if o.meeting_id in meeting_tz:
                                mtz = meeting_tz[o.meeting_id]
                            else:
                                mtz = pytz.timezone(o.meeting.time_zone)
                                meeting_tz[o.meeting_id] = mtz
                            aware = mtz.localize(value)
                        else:
                            aware = tzfrom.localize(value, is_dst=True)
                    except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
                        aware = value-datetime.timedelta(minutes=60)
                    except pytz.UnknownTimeZoneError as e:
                        assert e
                        # What would be a better handling here ??
                        #sys.stderr.write(f"\nUnknown time zone error for meeting {o.meeting.number}: {e}")
                        continue
                    conv = aware.astimezone(tzto).replace(tzinfo=None)
                    setattr(o, field.name, conv)
                    o.save()
                    converted[m] += 1
                else:
                    if not (this and orig):
                        nonevalue[m] += 1
                    else:
                        unchanged[m] += 1

    tau = time.time()-mark
    if count:
        looptime = (tau)*10**6/count
        sys.stderr.write(f'  {count:9,} {converted[m]:9,} {tau:5.1f}s {looptime:4.0f}µs\n')
    else:
        sys.stderr.write(f'  {count:9,} {0:9,} {tau:5.1f}s {0:4.0f}µs\n')
